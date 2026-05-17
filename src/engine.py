from src.ledgers import Ledger
from src.ledgers.service import LedgerService
from src.accounts import Account
from src.accounts.service import AccountService
from src.transfers import Transfer
from src.transfers.service import TransferService
from src.reporting.service import ReportingService


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
