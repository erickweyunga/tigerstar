from abc import ABC, abstractmethod

from src.ledgers.model import Ledger
from src.accounts.model import Account
from src.transfers.model import Transfer
from src.transfers.posting import Posting


class StorageBase(ABC):

    @abstractmethod
    def save_ledger(self, ledger: Ledger) -> None:
        ...

    @abstractmethod
    def get_ledger(self, ledger_id: str) -> Ledger | None:
        ...

    @abstractmethod
    def save_account(self, account: Account) -> None:
        ...

    @abstractmethod
    def save_accounts_batch(self, accounts: list[Account]) -> None:
        ...

    @abstractmethod
    def get_account(self, account_id: str) -> Account | None:
        ...

    @abstractmethod
    def get_accounts_batch(self, account_ids: list[str]) -> dict[str, Account]:
        ...

    @abstractmethod
    def save_transfer(self, transfer: Transfer) -> None:
        ...

    @abstractmethod
    def get_transfer(self, transfer_id: str) -> Transfer | None:
        ...

    @abstractmethod
    def save_posting(self, posting: Posting) -> None:
        ...

    @abstractmethod
    def get_postings_for_transfer(self, transfer_id: str) -> list[Posting]:
        ...

    @abstractmethod
    def execute_transfer(
        self,
        transfers: list[Transfer],
        callback,
    ) -> list[Transfer]:
        """
        Execute a batch of transfers atomically.
        The callback receives (get_accounts, get_transfers) helpers
        and returns (results, account_updates, transfer_writes, posting_writes).
        The storage layer wraps this in a transaction.
        """
        ...

    @abstractmethod
    def query_accounts_by_ledger(self, ledger_id: str) -> list[Account]:
        ...

    @abstractmethod
    def query_transfers_by_ledger(self, ledger_id: str) -> list[Transfer]:
        ...

    @abstractmethod
    def query_postings_by_account(self, account_id: str) -> list[Posting]:
        ...

    @abstractmethod
    def query_postings_all(self) -> list[Posting]:
        ...
