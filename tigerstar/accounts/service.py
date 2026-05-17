from tigerstar.accounts.model import Account
from tigerstar.core.exceptions import LedgerNotFound


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

        ledger_ids = {a.ledger_id for a in accounts}
        for lid in ledger_ids:
            ledger = self.storage.get_ledger(lid)
            if not ledger:
                raise LedgerNotFound(lid)

        self.storage.save_accounts_batch(accounts)
        return accounts

    def get(self, account_id: str) -> Account | None:
        return self.storage.get_account(account_id)

    def get_batch(self, account_ids: list[str]) -> dict[str, Account]:
        return self.storage.get_accounts_batch(account_ids)
