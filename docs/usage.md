# TigerStar Usage Guide

## Setup

```python
from src import (
    TigerStar,
    FirestoreStorage,
    Ledger,
    Account,
    AccountType,
    AccountFlags,
    Transfer,
    TransferCode,
    TransferFlags,
)

storage = FirestoreStorage(credentials_path="path/to/firebase-adminsdk.json")
engine = TigerStar(storage=storage)
```

## Creating a Ledger

Every account and transfer belongs to a ledger. A ledger defines the currency, precision, and optional transfer limits.

```python
ledger = Ledger(
    currency="TZS",
    precision=0,              # 0 decimal places (integer amounts)
    max_transfer_amount=10_000_000,  # optional cap per transfer
)
engine.create_ledger(ledger)
```

For currencies with decimals (e.g. USD), use `precision=2` and store amounts in cents:

```python
usd_ledger = Ledger(currency="USD", precision=2, max_transfer_amount=100_000)
```

## Creating Accounts

Accounts have a type and optional flags to enforce balance constraints.

### Account Types

| Type | Normal Balance | Use Case |
|------|---------------|----------|
| `ASSET` | Debit | Cash, bank holdings |
| `LIABILITY` | Credit | User wallets, payables |
| `EQUITY` | Credit | Owner's equity |
| `INCOME` | Credit | Fees, revenue |
| `EXPENSE` | Debit | Costs, payouts |

### Basic Accounts

```python
cash = Account(ledger_id=ledger.id, code=AccountType.ASSET)
fee_account = Account(ledger_id=ledger.id, code=AccountType.INCOME)
control = Account(ledger_id=ledger.id, code=AccountType.LIABILITY)
```

### User Accounts (with overdraft protection)

```python
user = Account(
    ledger_id=ledger.id,
    code=AccountType.LIABILITY,
    flags=AccountFlags(debits_must_not_exceed_credits=True),
)
```

This prevents the user from spending more than they've received.

### Batch Creation

```python
engine.create_accounts([cash, fee_account, control, user])
```

## Transfers

All money movement happens through transfers. Every transfer debits one account and credits another.

### Simple Transfer

```python
# Deposit 50,000 into user's account
engine.create_transfers([
    Transfer(
        debit_account_id=cash.id,
        credit_account_id=user.id,
        ledger_id=ledger.id,
        amount=50000,
        code=TransferCode.PAYMENT,
    ),
])
```

### Transfer Codes

| Code | Use |
|------|-----|
| `TRANSFER` | P2P, withdrawals, internal moves |
| `PAYMENT` | Deposits, charges, fees |
| `REFUND` | Reversing a payment back to user |
| `REVERSAL` | System-initiated reversal |
| `CORRECTION` | Fixing an error (audit trail) |

### User Data

Tag transfers with a string for correlation:

```python
Transfer(
    ...,
    user_data="order_abc_123",
)
```

## Two-Phase Transfers

Reserve funds first, then post or void later.

### Phase 1: Reserve (Pending)

```python
pending = Transfer(
    debit_account_id=user.id,
    credit_account_id=control.id,
    ledger_id=ledger.id,
    amount=10000,
    code=TransferCode.TRANSFER,
    flags=TransferFlags(pending=True),
)
engine.create_transfers([pending])
```

The amount moves to `debits_pending` on the debit account. The user's available balance decreases but `balance` (posted only) is unchanged until posting.

### Phase 2a: Post (Confirm)

```python
engine.create_transfers([
    Transfer(
        debit_account_id=user.id,
        credit_account_id=control.id,
        ledger_id=ledger.id,
        amount=10000,
        code=TransferCode.TRANSFER,
        flags=TransferFlags(post_pending_transfer=True),
        pending_id=pending.id,
    ),
])
```

Moves funds from pending to posted.

### Phase 2b: Void (Cancel)

```python
engine.create_transfers([
    Transfer(
        debit_account_id=user.id,
        credit_account_id=control.id,
        ledger_id=ledger.id,
        amount=10000,
        code=TransferCode.TRANSFER,
        flags=TransferFlags(void_pending_transfer=True),
        pending_id=pending.id,
    ),
])
```

Releases the reserved funds back.

### Partial Post

Post less than the reserved amount. The remainder is automatically released:

```python
# Reserved 10,000, only post 7,000
Transfer(
    ...,
    amount=7000,
    flags=TransferFlags(post_pending_transfer=True),
    pending_id=pending.id,
)
```

## Linked Transfers

Process multiple transfers atomically. If any fails, all fail:

```python
engine.create_transfers([
    Transfer(
        debit_account_id=user.id,
        credit_account_id=control.id,
        ledger_id=ledger.id,
        amount=10000,
        code=TransferCode.TRANSFER,
        flags=TransferFlags(linked=True),  # linked to next
    ),
    Transfer(
        debit_account_id=control.id,
        credit_account_id=fee_account.id,
        ledger_id=ledger.id,
        amount=500,
        code=TransferCode.PAYMENT,
        flags=TransferFlags(linked=True),  # linked to next
    ),
    Transfer(
        debit_account_id=control.id,
        credit_account_id=recipient.id,
        ledger_id=ledger.id,
        amount=9500,
        code=TransferCode.TRANSFER,
        # last in chain — no linked flag
    ),
])
```

All transfers in a single `create_transfers` call execute in one Firestore transaction.

## Common Patterns

### P2P Transfer with Fee

```python
# 1. Reserve from sender
pending = Transfer(
    debit_account_id=sender.id,
    credit_account_id=control.id,
    ledger_id=ledger.id,
    amount=10000,
    code=TransferCode.TRANSFER,
    flags=TransferFlags(pending=True),
    user_data="p2p_001",
)
engine.create_transfers([pending])

# 2. Post + split fee + pay recipient (atomic)
engine.create_transfers([
    Transfer(
        debit_account_id=sender.id,
        credit_account_id=control.id,
        ledger_id=ledger.id,
        amount=10000,
        code=TransferCode.TRANSFER,
        flags=TransferFlags(post_pending_transfer=True),
        pending_id=pending.id,
        user_data="p2p_001",
    ),
    Transfer(
        debit_account_id=control.id,
        credit_account_id=fee_account.id,
        ledger_id=ledger.id,
        amount=500,
        code=TransferCode.PAYMENT,
        flags=TransferFlags(linked=True),
        user_data="p2p_001",
    ),
    Transfer(
        debit_account_id=control.id,
        credit_account_id=recipient.id,
        ledger_id=ledger.id,
        amount=9500,
        code=TransferCode.TRANSFER,
        user_data="p2p_001",
    ),
])
```

### Correcting a Transfer

Never delete or modify transfers. Instead, reverse and re-apply:

```python
# Original was wrong (charged 5,000, should be 3,000)
engine.create_transfers([
    Transfer(
        debit_account_id=fee_account.id,
        credit_account_id=user.id,
        ledger_id=ledger.id,
        amount=5000,
        code=TransferCode.CORRECTION,
        user_data="order_xyz",
    ),
    Transfer(
        debit_account_id=user.id,
        credit_account_id=fee_account.id,
        ledger_id=ledger.id,
        amount=3000,
        code=TransferCode.PAYMENT,
        user_data="order_xyz",
    ),
])
```

### Currency Exchange

Use linked transfers across two ledgers with a liquidity provider:

```python
engine.create_transfers([
    Transfer(
        debit_account_id=user_tzs.id,
        credit_account_id=lp_tzs.id,
        ledger_id=tzs_ledger.id,
        amount=10000,
        code=TransferCode.TRANSFER,
        flags=TransferFlags(linked=True),
        user_data="exchange_001",
    ),
    Transfer(
        debit_account_id=lp_usd.id,
        credit_account_id=user_usd.id,
        ledger_id=usd_ledger.id,
        amount=400,  # 10,000 TZS at 2500:1
        code=TransferCode.TRANSFER,
        user_data="exchange_001",
    ),
])
```

## Reporting

```python
# Trial balance — debits must equal credits
tb = engine.reporting.trial_balance(ledger.id)
print(tb["balanced"])  # True

# Balance sheet — assets = liabilities + equity + income - expenses
bs = engine.reporting.balance_sheet(ledger.id)
print(bs["balanced"])  # True

# General ledger — all postings, optionally filtered by account
entries = engine.reporting.general_ledger(ledger.id, account_id=user.id)
```

## Error Handling

```python
from src.core.exceptions import (
    InsufficientFunds,
    AccountNotFound,
    LedgerNotFound,
    CrossLedgerTransfer,
    TransferLimitExceeded,
)

try:
    engine.create_transfers([...])
except InsufficientFunds:
    print("Not enough balance")
except TransferLimitExceeded:
    print("Amount exceeds ledger limit")
```

## Account Balance

```python
account = storage.get_account(account_id)

account.balance          # posted balance (normal balance for account type)
account.debits_posted    # total debits posted
account.credits_posted   # total credits posted
account.debits_pending   # reserved debits (not yet posted)
account.credits_pending  # reserved credits (not yet posted)
```

For LIABILITY accounts (users), available balance is:

```python
available = account.balance - account.debits_pending
```
