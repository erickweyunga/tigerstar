from src.ledgers.model import Ledger


class LedgerService:

    def __init__(self, storage):
        self.storage = storage

    def create(self, ledger: Ledger) -> Ledger:
        existing = self.storage.get_ledger(ledger.id)
        if existing:
            raise ValueError("Ledger already exists")
        self.storage.save_ledger(ledger)
        return ledger

    def get(self, ledger_id: str) -> Ledger | None:
        return self.storage.get_ledger(ledger_id)
