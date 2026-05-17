from src.accounts.model import Account
from src.core.exceptions import LedgerNotFound


class AccountService:

    def __init__(self, storage):
        self.storage = storage

    def create(self, account: Account) -> Account:
        ledger = self.storage.get_ledger(account.ledger_id)
        if not ledger:
            raise LedgerNotFound(account.ledger_id)
        self.storage.save_account(account)
        return account

    def create_batch(self, accounts: list[Account]) -> list[Account]:
        if not accounts:
            return []

        # validate ledger once (all accounts must be same ledger for batch)
        ledger_ids = {a.ledger_id for a in accounts}
        for lid in ledger_ids:
            ledger = self.storage.get_ledger(lid)
            if not ledger:
                raise LedgerNotFound(lid)

        # batch write all accounts in one round-trip
        batch = self.storage.db.batch()
        for account in accounts:
            batch.set(
                self.storage.accounts.document(account.id),
                self.storage._serialize_account(account),
            )
        batch.commit()

        return accounts

    def get(self, account_id: str) -> Account | None:
        return self.storage.get_account(account_id)

    def get_batch(self, account_ids: list[str]) -> list[Account]:
        refs = [self.storage.accounts.document(aid) for aid in account_ids]
        docs = self.storage.db.get_all(refs)
        results = []
        for doc in docs:
            if doc.exists:
                results.append(self.storage._deserialize_account(doc.to_dict()))
        return results
