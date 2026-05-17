class LedgerError(Exception):
    pass


class LedgerNotFound(LedgerError):
    pass


class AccountNotFound(LedgerError):
    pass


class DuplicateTransfer(LedgerError):
    pass


class InsufficientFunds(LedgerError):
    pass


class CrossLedgerTransfer(LedgerError):
    pass


class InvalidAmount(LedgerError):
    pass


class TransferLimitExceeded(LedgerError):
    pass
