# Storage Adapters

TigerStar uses a storage adapter pattern. The engine doesn't care which database you use — swap the adapter and everything works the same.

## Available Adapters

| Adapter | Database | Best For |
|---------|----------|----------|
| `FirestoreStorage` | Google Cloud Firestore | Serverless, zero-ops, auto-scaling |
| `PostgresStorage` | PostgreSQL | Financial-grade ACID, SQL flexibility, cost control |

## Firestore Adapter

```python
from tigerstar import TigerStar, FirestoreStorage

storage = FirestoreStorage(
    credentials_path="path/to/firebase-adminsdk.json",
    database_id="default",  # optional, defaults to "default"
)
engine = TigerStar(storage=storage)
```

### Requirements

- `firebase-admin` package
- A Firebase project with Firestore enabled
- Service account JSON credentials

### Collections Created

- `ledgers`
- `accounts`
- `transfers`
- `postings`

### Notes

- Transactions use Firestore's built-in optimistic concurrency
- All reads happen before writes within a transaction
- Scales automatically — no infrastructure to manage
- Pay per read/write operation

## PostgreSQL Adapter

```python
from tigerstar import TigerStar, PostgresStorage

storage = PostgresStorage(
    dsn="postgresql://user:password@localhost:5432/dbname",
    min_size=5,   # minimum pool connections
    max_size=20,  # maximum pool connections
)
storage.migrate()  # create tables on first run
engine = TigerStar(storage=storage)
```

### Requirements

- `psycopg[binary]` and `psycopg-pool` packages
- PostgreSQL 15+ (recommended: 17+)

### Connection Pooling

The adapter uses `psycopg_pool.ConnectionPool` internally. Connections are reused across requests — no per-operation connection overhead.

```python
# Custom pool sizing for high-throughput
storage = PostgresStorage(
    dsn="postgresql://user:pass@localhost/otta",
    min_size=10,   # keep 10 connections warm
    max_size=50,   # burst up to 50 under load
)
```

For production with multiple app instances, put PgBouncer in front of PostgreSQL:

```python
# Point at PgBouncer (transaction pooling mode)
storage = PostgresStorage(
    dsn="postgresql://user:pass@localhost:6432/otta",
    min_size=5,
    max_size=20,
)
```

### Migrations

Tables are created via SQL migration files in `src/storage/postgres/`.

**Option 1 — via the storage instance:**

```python
storage = PostgresStorage(dsn="postgresql://...")
storage.migrate()
```

**Option 2 — import and run directly:**

```python
import psycopg
from tigerstar.storage.postgres import run_migrations

conn = psycopg.connect("postgresql://user:pass@localhost/otta", autocommit=True)
run_migrations(conn)
conn.close()
```

Migrations are versioned. Each `.sql` file runs once — tracked in a `schema_migrations` table. To add a new migration, create a new file like `002_add_column.sql` in the `src/storage/postgres/` folder.

### Concurrency

- Uses `SELECT ... FOR UPDATE` with deterministic lock ordering
- Account IDs are sorted before locking — prevents deadlocks
- Ledger validation runs outside the transaction to minimize lock hold time
- Read Committed isolation level (default) + explicit row locks

### Schema Constraints

The database enforces integrity at the SQL level:

- `CHECK (amount > 0)` — no zero or negative transfers
- `CHECK (debit_account_id != credit_account_id)` — can't transfer to self
- `CHECK (debits_pending >= 0 ...)` — balances never go negative
- Foreign keys on all references

### Indexes

Optimized for ledger workloads:

- Covering index on `transfers(ledger_id, created_at)` — avoids heap lookups
- Partial index on pending transfers — fast timeout queries
- Composite index on `postings(account_id, created_at)` — fast general ledger queries

## Writing a Custom Adapter

Implement `StorageBase`:

```python
from tigerstar.storage.base import StorageBase

class MyStorage(StorageBase):

    def save_ledger(self, ledger):
        ...

    def get_ledger(self, ledger_id):
        ...

    def save_account(self, account):
        ...

    def save_accounts_batch(self, accounts):
        ...

    def get_account(self, account_id):
        ...

    def get_accounts_batch(self, account_ids):
        ...

    def save_transfer(self, transfer):
        ...

    def get_transfer(self, transfer_id):
        ...

    def save_posting(self, posting):
        ...

    def get_postings_for_transfer(self, transfer_id):
        ...

    def execute_transfer(self, transfers, account_ids, pending_ids, process):
        """
        Must be atomic. Steps:
        1. Read pending transfers by pending_ids (if any)
        2. Read and lock accounts by account_ids
        3. Call process(accounts, pending_transfers) -> (results, updated_accounts, postings)
        4. Write updated accounts, new transfers, and postings
        5. Return results
        All within a single transaction.
        """
        ...

    def query_accounts_by_ledger(self, ledger_id):
        ...

    def query_transfers_by_ledger(self, ledger_id):
        ...

    def query_postings_by_account(self, account_id):
        ...

    def query_postings_all(self):
        ...
```

Then use it:

```python
storage = MyStorage(...)
engine = TigerStar(storage=storage)
```
