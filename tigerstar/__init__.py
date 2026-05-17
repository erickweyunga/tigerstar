from tigerstar.core import AccountType, AccountFlags, TransferCode, TransferFlags, PostingType
from tigerstar.ledgers import Ledger
from tigerstar.accounts import Account
from tigerstar.transfers import Transfer, Posting
from tigerstar.engine import TigerStar


def __getattr__(name):
    if name == "FirestoreStorage":
        from tigerstar.storage.firestore import FirestoreStorage
        return FirestoreStorage
    if name == "PostgresStorage":
        from tigerstar.storage.postgres import PostgresStorage
        return PostgresStorage
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "AccountType",
    "AccountFlags",
    "TransferCode",
    "TransferFlags",
    "PostingType",
    "Ledger",
    "Account",
    "Transfer",
    "Posting",
    "FirestoreStorage",
    "PostgresStorage",
    "TigerStar",
]
