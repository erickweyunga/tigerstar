from dataclasses import dataclass, field
from datetime import datetime, timezone

from src.core.types import AccountType, AccountFlags
from src.core.identity import generate_id


@dataclass(frozen=True)
class Account:
    ledger_id: str
    code: AccountType

    debits_pending: int = 0
    debits_posted: int = 0
    credits_pending: int = 0
    credits_posted: int = 0

    flags: AccountFlags = field(default_factory=AccountFlags)
    id: str = field(default_factory=generate_id)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def balance(self) -> int:
        if self.code in (AccountType.ASSET, AccountType.EXPENSE):
            return self.debits_posted - self.credits_posted
        return self.credits_posted - self.debits_posted
