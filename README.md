# TigerStar

A double-entry ledger engine with pluggable storage backends.

## Features

- **Double-entry bookkeeping** — every transfer debits one account and credits another
- **Two-phase transfers** — reserve funds (pending), then post or void
- **Linked transfers** — atomic chains that all succeed or all fail
- **Balance constraints** — prevent overdrafts with account flags
- **Multi-currency** — separate ledgers per currency with configurable precision
- **Financial reporting** — trial balance, balance sheet, general ledger
- **Storage adapters** — swap between Firestore and PostgreSQL without changing application code
- **Concurrent-safe** — row-level locking (Postgres) or optimistic transactions (Firestore)

## Install

```bash
pip install tigerstar[postgres]    # PostgreSQL only
pip install tigerstar[firestore]   # Firestore only
pip install tigerstar[all]         # both backends
```

## Quick Start

### With Firestore

```python
from tigerstar import TigerStar, FirestoreStorage

storage = FirestoreStorage(credentials_path="path/to/firebase-adminsdk.json")
engine = TigerStar(storage=storage)
```

### With PostgreSQL

```python
from tigerstar import TigerStar, PostgresStorage

storage = PostgresStorage(dsn="postgresql://user:pass@localhost:5432/dbname")
storage.migrate()
engine = TigerStar(storage=storage)
```

### Create a ledger and move money

```python
from tigerstar import Ledger, Account, AccountType, AccountFlags, Transfer, TransferCode

ledger = Ledger(currency="TZS", precision=0, max_transfer_amount=10_000_000)
engine.create_ledger(ledger)

cash = Account(ledger_id=ledger.id, code=AccountType.ASSET)
user = Account(
    ledger_id=ledger.id,
    code=AccountType.LIABILITY,
    flags=AccountFlags(debits_must_not_exceed_credits=True),
)
engine.create_accounts([cash, user])

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

## Storage Adapters

| Adapter | Database | Best For |
|---------|----------|----------|
| `FirestoreStorage` | Google Cloud Firestore | Serverless, zero-ops, auto-scaling |
| `PostgresStorage` | PostgreSQL | Financial-grade ACID, SQL flexibility, cost control |

Both adapters implement the same interface — swap one for the other with zero application changes. See [docs/adapters.md](docs/adapters.md) for connection pooling, migrations, and writing custom adapters.

## Documentation

- [Usage Guide](docs/usage.md) — ledgers, accounts, transfers, reporting
- [Storage Adapters](docs/adapters.md) — setup, configuration, custom adapters
