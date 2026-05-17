from tigerstar.ledgers import Ledger
from tigerstar.ledgers.service import LedgerService
from tigerstar.accounts import Account
from tigerstar.accounts.service import AccountService
from tigerstar.transfers import Transfer
from tigerstar.transfers.service import TransferService
from tigerstar.reporting.service import ReportingService


class TigerStar:

    def __init__(self, storage):
        self.storage = storage
        self.ledgers = LedgerService(storage)
        self.accounts = AccountService(storage)
        self.transfers = TransferService(storage)
        self.reporting = ReportingService(storage)

    def create_ledger(self, ledger: Ledger) -> Ledger:
        return self.ledgers.create(ledger)

    def create_account(self, account: Account) -> Account:
        return self.accounts.create(account)

    def create_accounts(self, accounts: list[Account]) -> list[Account]:
        return self.accounts.create_batch(accounts)

    def create_transfers(self, transfers: list[Transfer]) -> list[Transfer]:
        return self.transfers.create(transfers)
