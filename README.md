# TigerStar

A double-entry ledger engine backed by Google Cloud Firestore.

## Features

- **Double-entry bookkeeping** — every transfer debits one account and credits another
- **Two-phase transfers** — reserve funds (pending), then post or void
- **Linked transfers** — atomic chains that all succeed or all fail
- **Balance constraints** — prevent overdrafts with account flags
- **Multi-currency** — separate ledgers per currency with configurable precision
- **Financial reporting** — trial balance, balance sheet, general ledger
- **Concurrent-safe** — Firestore transactions serialize access to shared accounts

## Quick Start

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

# create a ledger
ledger = Ledger(currency="TZS", precision=0, max_transfer_amount=10_000_000)
engine.create_ledger(ledger)

# create accounts
cash = Account(ledger_id=ledger.id, code=AccountType.ASSET)
user = Account(
    ledger_id=ledger.id,
    code=AccountType.LIABILITY,
    flags=AccountFlags(debits_must_not_exceed_credits=True),
)
engine.create_accounts([cash, user])

# deposit
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

## Project Structure

```
src/
  core/         types, exceptions, ID generation
  ledgers/      ledger model and service
  accounts/     account model and service
  transfers/    transfer model, postings, service
  storage/      Firestore persistence layer
  reporting/    trial balance, balance sheet, general ledger
  engine.py     TigerStar facade
docs/
  usage.md      full usage guide
```

## Documentation

See [docs/usage.md](docs/usage.md) for the full usage guide covering:

- Ledger and account setup
- Simple and two-phase transfers
- Linked transfers and fee splitting
- P2P payments, corrections, currency exchange
- Reporting and error handling
