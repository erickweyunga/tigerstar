from .base import StorageBase


def __getattr__(name):
    if name == "FirestoreStorage":
        from .firestore import FirestoreStorage
        return FirestoreStorage
    if name == "PostgresStorage":
        from .postgres import PostgresStorage
        return PostgresStorage
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["StorageBase", "FirestoreStorage", "PostgresStorage"]
