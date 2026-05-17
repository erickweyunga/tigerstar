from dataclasses import dataclass, field
from datetime import datetime, timezone

from tigerstar.core.types import PostingType
from tigerstar.core.identity import generate_id


@dataclass(frozen=True)
class Posting:
    transfer_id: str
    account_id: str
    posting_type: PostingType
    amount: int

    id: str = field(default_factory=generate_id)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
