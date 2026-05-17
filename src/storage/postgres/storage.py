import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from src.storage.base import StorageBase
from src.storage.postgres.migrations import run_migrations
from src.ledgers.model import Ledger
from src.accounts.model import Account
from src.transfers.model import Transfer
from src.transfers.posting import Posting
from src.core.types import AccountType, AccountFlags, TransferCode, TransferFlags, PostingType
from src.core.exceptions import AccountNotFound


class PostgresStorage(StorageBase):

    def __init__(self, dsn: str, min_size: int = 5, max_size: int = 20):
        self.dsn = dsn
        self.pool = ConnectionPool(
            conninfo=dsn,
            min_size=min_size,
            max_size=max_size,
            kwargs={"row_factory": dict_row, "autocommit": True},
        )

    def migrate(self):
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                run_migrations(conn)

    def close(self):
        self.pool.close()

    # --- ledgers ---

    def save_ledger(self, ledger: Ledger):
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """INSERT INTO ledgers (id, currency, precision_, max_transfer_amount, created_at)
                   VALUES (%(id)s, %(currency)s, %(precision)s, %(max_transfer_amount)s, %(created_at)s)
                   ON CONFLICT (id) DO UPDATE SET
                     currency = EXCLUDED.currency,
                     precision_ = EXCLUDED.precision_,
                     max_transfer_amount = EXCLUDED.max_transfer_amount""",
                {
                    "id": ledger.id,
                    "currency": ledger.currency,
                    "precision": ledger.precision,
                    "max_transfer_amount": ledger.max_transfer_amount,
                    "created_at": ledger.created_at,
                },
            )

    def get_ledger(self, ledger_id: str) -> Ledger | None:
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM ledgers WHERE id = %s", (ledger_id,))
            row = cur.fetchone()
        if not row:
            return None
        return self._row_to_ledger(row)

    # --- accounts ---

    def save_account(self, account: Account):
        with self.pool.connection() as conn, conn.cursor() as cur:
            self._upsert_account(cur, account)

    def save_accounts_batch(self, accounts: list[Account]):
        with self.pool.connection() as conn, conn.cursor() as cur:
            for account in accounts:
                self._upsert_account(cur, account)

    def get_account(self, account_id: str) -> Account | None:
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM accounts WHERE id = %s", (account_id,))
            row = cur.fetchone()
        if not row:
            return None
        return self._row_to_account(row)

    def get_accounts_batch(self, account_ids: list[str]) -> dict[str, Account]:
        if not account_ids:
            return {}
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM accounts WHERE id = ANY(%s)",
                (account_ids,),
            )
            rows = cur.fetchall()
        return {row["id"]: self._row_to_account(row) for row in rows}

    # --- transfers ---

    def save_transfer(self, transfer: Transfer):
        with self.pool.connection() as conn, conn.cursor() as cur:
            self._insert_transfer(cur, transfer)

    def get_transfer(self, transfer_id: str) -> Transfer | None:
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM transfers WHERE id = %s", (transfer_id,))
            row = cur.fetchone()
        if not row:
            return None
        return self._row_to_transfer(row)

    # --- postings ---

    def save_posting(self, posting: Posting):
        with self.pool.connection() as conn, conn.cursor() as cur:
            self._insert_posting(cur, posting)

    def get_postings_for_transfer(self, transfer_id: str) -> list[Posting]:
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM postings WHERE transfer_id = %s ORDER BY created_at",
                (transfer_id,),
            )
            return [self._row_to_posting(row) for row in cur.fetchall()]

    # --- transactional transfer execution ---

    def execute_transfer(self, transfers, account_ids, pending_ids, process):
        with self.pool.connection() as conn:
          with conn.transaction():
            with conn.cursor() as cur:
                pending_transfers = {}
                if pending_ids:
                    cur.execute(
                        "SELECT * FROM transfers WHERE id = ANY(%s)",
                        (pending_ids,),
                    )
                    for row in cur.fetchall():
                        pt = self._row_to_transfer(row)
                        pending_transfers[pt.id] = pt
                        account_ids.append(pt.debit_account_id)
                        account_ids.append(pt.credit_account_id)

                    if len(pending_transfers) != len(pending_ids):
                        raise ValueError("Pending transfer not found")

                unique_ids = sorted(set(account_ids))
                accounts = {}
                if unique_ids:
                    cur.execute(
                        "SELECT * FROM accounts WHERE id = ANY(%s) ORDER BY id FOR UPDATE",
                        (unique_ids,),
                    )
                    for row in cur.fetchall():
                        accounts[row["id"]] = self._row_to_account(row)

                    for aid in unique_ids:
                        if aid not in accounts:
                            raise AccountNotFound(aid)

                results, updated_accounts, postings = process(accounts, pending_transfers)

                for aid, account in updated_accounts.items():
                    cur.execute(
                        """UPDATE accounts SET
                             debits_pending = %(dp)s,
                             debits_posted = %(dpo)s,
                             credits_pending = %(cp)s,
                             credits_posted = %(cpo)s
                           WHERE id = %(id)s""",
                        {
                            "id": aid,
                            "dp": account.debits_pending,
                            "dpo": account.debits_posted,
                            "cp": account.credits_pending,
                            "cpo": account.credits_posted,
                        },
                    )

                for result in results:
                    self._insert_transfer(cur, result)

                for posting in postings:
                    self._insert_posting(cur, posting)

                return results

    # --- queries ---

    def query_accounts_by_ledger(self, ledger_id: str) -> list[Account]:
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM accounts WHERE ledger_id = %s",
                (ledger_id,),
            )
            return [self._row_to_account(row) for row in cur.fetchall()]

    def query_transfers_by_ledger(self, ledger_id: str) -> list[Transfer]:
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM transfers WHERE ledger_id = %s ORDER BY created_at",
                (ledger_id,),
            )
            return [self._row_to_transfer(row) for row in cur.fetchall()]

    def query_postings_by_account(self, account_id: str) -> list[Posting]:
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM postings WHERE account_id = %s ORDER BY created_at",
                (account_id,),
            )
            return [self._row_to_posting(row) for row in cur.fetchall()]

    def query_postings_all(self) -> list[Posting]:
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM postings ORDER BY created_at")
            return [self._row_to_posting(row) for row in cur.fetchall()]

    # --- helpers ---

    def _upsert_account(self, cur, account: Account):
        cur.execute(
            """INSERT INTO accounts (id, ledger_id, code, debits_pending, debits_posted,
                 credits_pending, credits_posted, flag_debits_must_not_exceed_credits,
                 flag_credits_must_not_exceed_debits, created_at)
               VALUES (%(id)s, %(ledger_id)s, %(code)s, %(dp)s, %(dpo)s, %(cp)s, %(cpo)s,
                 %(f1)s, %(f2)s, %(created_at)s)
               ON CONFLICT (id) DO UPDATE SET
                 debits_pending = EXCLUDED.debits_pending,
                 debits_posted = EXCLUDED.debits_posted,
                 credits_pending = EXCLUDED.credits_pending,
                 credits_posted = EXCLUDED.credits_posted""",
            {
                "id": account.id,
                "ledger_id": account.ledger_id,
                "code": account.code.value,
                "dp": account.debits_pending,
                "dpo": account.debits_posted,
                "cp": account.credits_pending,
                "cpo": account.credits_posted,
                "f1": account.flags.debits_must_not_exceed_credits,
                "f2": account.flags.credits_must_not_exceed_debits,
                "created_at": account.created_at,
            },
        )

    def _insert_transfer(self, cur, transfer: Transfer):
        cur.execute(
            """INSERT INTO transfers (id, debit_account_id, credit_account_id, ledger_id,
                 amount, code, flag_linked, flag_pending, flag_post_pending_transfer,
                 flag_void_pending_transfer, pending_id, user_data, timeout, created_at)
               VALUES (%(id)s, %(debit)s, %(credit)s, %(ledger)s, %(amount)s, %(code)s,
                 %(linked)s, %(pending)s, %(post)s, %(void)s, %(pending_id)s,
                 %(user_data)s, %(timeout)s, %(created_at)s)""",
            {
                "id": transfer.id,
                "debit": transfer.debit_account_id,
                "credit": transfer.credit_account_id,
                "ledger": transfer.ledger_id,
                "amount": transfer.amount,
                "code": transfer.code.value,
                "linked": transfer.flags.linked,
                "pending": transfer.flags.pending,
                "post": transfer.flags.post_pending_transfer,
                "void": transfer.flags.void_pending_transfer,
                "pending_id": transfer.pending_id,
                "user_data": transfer.user_data,
                "timeout": transfer.timeout,
                "created_at": transfer.created_at,
            },
        )

    def _insert_posting(self, cur, posting: Posting):
        cur.execute(
            """INSERT INTO postings (id, transfer_id, account_id, posting_type, amount, created_at)
               VALUES (%(id)s, %(transfer_id)s, %(account_id)s, %(type)s, %(amount)s, %(created_at)s)""",
            {
                "id": posting.id,
                "transfer_id": posting.transfer_id,
                "account_id": posting.account_id,
                "type": posting.posting_type.value,
                "amount": posting.amount,
                "created_at": posting.created_at,
            },
        )

    # --- row mapping ---

    def _row_to_ledger(self, row: dict) -> Ledger:
        return Ledger(
            id=row["id"],
            currency=row["currency"],
            precision=row["precision_"],
            max_transfer_amount=row["max_transfer_amount"],
            created_at=row["created_at"],
        )

    def _row_to_account(self, row: dict) -> Account:
        return Account(
            id=row["id"],
            ledger_id=row["ledger_id"],
            code=AccountType(row["code"]),
            debits_pending=row["debits_pending"],
            debits_posted=row["debits_posted"],
            credits_pending=row["credits_pending"],
            credits_posted=row["credits_posted"],
            flags=AccountFlags(
                debits_must_not_exceed_credits=row["flag_debits_must_not_exceed_credits"],
                credits_must_not_exceed_debits=row["flag_credits_must_not_exceed_debits"],
            ),
            created_at=row["created_at"],
        )

    def _row_to_transfer(self, row: dict) -> Transfer:
        return Transfer(
            id=row["id"],
            debit_account_id=row["debit_account_id"],
            credit_account_id=row["credit_account_id"],
            ledger_id=row["ledger_id"],
            amount=row["amount"],
            code=TransferCode(row["code"]),
            flags=TransferFlags(
                linked=row["flag_linked"],
                pending=row["flag_pending"],
                post_pending_transfer=row["flag_post_pending_transfer"],
                void_pending_transfer=row["flag_void_pending_transfer"],
            ),
            pending_id=row["pending_id"],
            user_data=row["user_data"],
            timeout=row["timeout"],
            created_at=row["created_at"],
        )

    def _row_to_posting(self, row: dict) -> Posting:
        return Posting(
            id=row["id"],
            transfer_id=row["transfer_id"],
            account_id=row["account_id"],
            posting_type=PostingType(row["posting_type"]),
            amount=row["amount"],
            created_at=row["created_at"],
        )
