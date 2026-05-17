from dataclasses import dataclass, field
from datetime import datetime

from src.core.types import PostingType
from src.core.identity import generate_id


@dataclass(frozen=True)
class Posting:
    transfer_id: str
    account_id: str
    posting_type: PostingType
    amount: int

    id: str = field(default_factory=generate_id)
    created_at: datetime = field(default_factory=datetime.utcnow)
