from dataclasses import dataclass, field
from datetime import datetime, timezone

from src.core.types import TransferCode, TransferFlags
from src.core.identity import generate_id


@dataclass(frozen=True)
class Transfer:
    debit_account_id: str
    credit_account_id: str
    ledger_id: str
    amount: int
    code: TransferCode

    flags: TransferFlags = field(default_factory=TransferFlags)
    pending_id: str | None = None
    user_data: str | None = None
    timeout: int | None = None
    id: str = field(default_factory=generate_id)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        if self.amount <= 0:
            raise ValueError("Transfer amount must be positive")
