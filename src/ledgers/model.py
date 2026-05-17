from dataclasses import dataclass, field
from datetime import datetime, timezone

from src.core.identity import generate_id


@dataclass(frozen=True)
class Ledger:
    currency: str
    precision: int = 2
    max_transfer_amount: int | None = None
    id: str = field(default_factory=generate_id)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
