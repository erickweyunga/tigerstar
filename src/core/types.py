from enum import Enum
from dataclasses import dataclass


class AccountType(str, Enum):
    ASSET = "ASSET"
    LIABILITY = "LIABILITY"
    EQUITY = "EQUITY"
    INCOME = "INCOME"
    EXPENSE = "EXPENSE"


class TransferCode(str, Enum):
    TRANSFER = "TRANSFER"
    PAYMENT = "PAYMENT"
    REFUND = "REFUND"
    REVERSAL = "REVERSAL"
    CORRECTION = "CORRECTION"


class PostingType(str, Enum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


@dataclass(frozen=True)
class AccountFlags:
    debits_must_not_exceed_credits: bool = False
    credits_must_not_exceed_debits: bool = False


@dataclass(frozen=True)
class TransferFlags:
    linked: bool = False
    pending: bool = False
    post_pending_transfer: bool = False
    void_pending_transfer: bool = False
