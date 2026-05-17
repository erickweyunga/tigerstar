from dataclasses import replace

from tigerstar.transfers.model import Transfer
from tigerstar.transfers.posting import Posting
from tigerstar.core.types import PostingType
from tigerstar.core.exceptions import (
    AccountNotFound,
    LedgerNotFound,
    InsufficientFunds,
    CrossLedgerTransfer,
    TransferLimitExceeded,
)


class TransferService:

    def __init__(self, storage):
        self.storage = storage

    def create(self, transfers: list[Transfer]) -> list[Transfer]:
        if not transfers:
            raise ValueError("Must provide at least one transfer")

        def process(accounts: dict, pending_transfers: dict) -> tuple:
            results = []
            postings = []

            for transfer in transfers:
                if transfer.flags.post_pending_transfer:
                    result = self._apply_post_pending(transfer, pending_transfers, accounts)
                elif transfer.flags.void_pending_transfer:
                    result = self._apply_void_pending(transfer, pending_transfers, accounts)
                elif transfer.flags.pending:
                    result = self._apply_pending(transfer, accounts)
                else:
                    result = self._apply_single_phase(transfer, accounts)

                results.append(result)
                postings.append(Posting(
                    transfer_id=result.id,
                    account_id=result.debit_account_id,
                    posting_type=PostingType.DEBIT,
                    amount=result.amount,
                ))
                postings.append(Posting(
                    transfer_id=result.id,
                    account_id=result.credit_account_id,
                    posting_type=PostingType.CREDIT,
                    amount=result.amount,
                ))

            return results, accounts, postings

        account_ids = set()
        pending_ids = []

        for transfer in transfers:
            if transfer.flags.post_pending_transfer or transfer.flags.void_pending_transfer:
                if not transfer.pending_id:
                    raise ValueError("post/void pending requires pending_id")
                pending_ids.append(transfer.pending_id)
            else:
                account_ids.add(transfer.debit_account_id)
                account_ids.add(transfer.credit_account_id)

        for transfer in transfers:
            if not (transfer.flags.post_pending_transfer or transfer.flags.void_pending_transfer):
                self._validate_ledger(transfer)

        return self.storage.execute_transfer(
            transfers=transfers,
            account_ids=list(account_ids),
            pending_ids=pending_ids,
            process=process,
        )

    def _apply_single_phase(self, transfer: Transfer, accounts: dict) -> Transfer:
        debit = accounts[transfer.debit_account_id]
        credit = accounts[transfer.credit_account_id]

        if debit.ledger_id != transfer.ledger_id:
            raise CrossLedgerTransfer(f"Debit account belongs to ledger {debit.ledger_id}")
        if credit.ledger_id != transfer.ledger_id:
            raise CrossLedgerTransfer(f"Credit account belongs to ledger {credit.ledger_id}")

        if debit.flags.debits_must_not_exceed_credits:
            if debit.debits_posted + transfer.amount > debit.credits_posted:
                raise InsufficientFunds()

        if credit.flags.credits_must_not_exceed_debits:
            if credit.credits_posted + transfer.amount > credit.debits_posted:
                raise InsufficientFunds()

        accounts[transfer.debit_account_id] = replace(
            debit, debits_posted=debit.debits_posted + transfer.amount
        )
        accounts[transfer.credit_account_id] = replace(
            credit, credits_posted=credit.credits_posted + transfer.amount
        )
        return transfer

    def _apply_pending(self, transfer: Transfer, accounts: dict) -> Transfer:
        debit = accounts[transfer.debit_account_id]
        credit = accounts[transfer.credit_account_id]

        if debit.ledger_id != transfer.ledger_id:
            raise CrossLedgerTransfer(f"Debit account belongs to ledger {debit.ledger_id}")
        if credit.ledger_id != transfer.ledger_id:
            raise CrossLedgerTransfer(f"Credit account belongs to ledger {credit.ledger_id}")

        total_debits = debit.debits_pending + debit.debits_posted + transfer.amount
        if debit.flags.debits_must_not_exceed_credits:
            if total_debits > debit.credits_posted:
                raise InsufficientFunds()

        total_credits = credit.credits_pending + credit.credits_posted + transfer.amount
        if credit.flags.credits_must_not_exceed_debits:
            if total_credits > credit.debits_posted:
                raise InsufficientFunds()

        accounts[transfer.debit_account_id] = replace(
            debit, debits_pending=debit.debits_pending + transfer.amount
        )
        accounts[transfer.credit_account_id] = replace(
            credit, credits_pending=credit.credits_pending + transfer.amount
        )
        return transfer

    def _apply_post_pending(self, transfer: Transfer, pending_transfers: dict, accounts: dict) -> Transfer:
        pending = pending_transfers[transfer.pending_id]
        if not pending.flags.pending:
            raise ValueError("Referenced transfer is not pending")

        post_amount = transfer.amount if transfer.amount <= pending.amount else pending.amount
        debit = accounts[pending.debit_account_id]
        credit = accounts[pending.credit_account_id]

        accounts[pending.debit_account_id] = replace(
            debit,
            debits_pending=debit.debits_pending - pending.amount,
            debits_posted=debit.debits_posted + post_amount,
        )
        accounts[pending.credit_account_id] = replace(
            credit,
            credits_pending=credit.credits_pending - pending.amount,
            credits_posted=credit.credits_posted + post_amount,
        )

        return replace(
            transfer,
            debit_account_id=pending.debit_account_id,
            credit_account_id=pending.credit_account_id,
            ledger_id=pending.ledger_id,
            amount=post_amount,
        )

    def _apply_void_pending(self, transfer: Transfer, pending_transfers: dict, accounts: dict) -> Transfer:
        pending = pending_transfers[transfer.pending_id]
        if not pending.flags.pending:
            raise ValueError("Referenced transfer is not pending")

        debit = accounts[pending.debit_account_id]
        credit = accounts[pending.credit_account_id]

        accounts[pending.debit_account_id] = replace(
            debit, debits_pending=debit.debits_pending - pending.amount
        )
        accounts[pending.credit_account_id] = replace(
            credit, credits_pending=credit.credits_pending - pending.amount
        )

        return replace(
            transfer,
            debit_account_id=pending.debit_account_id,
            credit_account_id=pending.credit_account_id,
            ledger_id=pending.ledger_id,
            amount=pending.amount,
        )

    def _validate_ledger(self, transfer: Transfer):
        ledger = self.storage.get_ledger(transfer.ledger_id)
        if not ledger:
            raise LedgerNotFound(transfer.ledger_id)
        if ledger.max_transfer_amount and transfer.amount > ledger.max_transfer_amount:
            raise TransferLimitExceeded(
                f"Amount {transfer.amount} exceeds ledger limit {ledger.max_transfer_amount}"
            )
