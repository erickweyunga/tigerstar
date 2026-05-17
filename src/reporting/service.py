from google.cloud.firestore_v1.base_query import FieldFilter

from src.core.types import AccountType


class ReportingService:

    def __init__(self, storage):
        self.storage = storage

    def trial_balance(self, ledger_id: str) -> dict:
        """
        Trial balance: sum of all debits must equal sum of all credits.
        Returns per-account debits/credits and totals.
        """
        accounts = self._get_accounts_for_ledger(ledger_id)

        rows = []
        total_debits = 0
        total_credits = 0

        for acc in accounts:
            rows.append({
                "account_id": acc.id,
                "code": acc.code.value,
                "debits": acc.debits_posted,
                "credits": acc.credits_posted,
            })
            total_debits += acc.debits_posted
            total_credits += acc.credits_posted

        return {
            "ledger_id": ledger_id,
            "rows": rows,
            "total_debits": total_debits,
            "total_credits": total_credits,
            "balanced": total_debits == total_credits,
        }

    def balance_sheet(self, ledger_id: str) -> dict:
        """
        Balance sheet: Assets = Liabilities + Equity + Income - Expenses.
        Groups accounts by type and shows balances.
        """
        accounts = self._get_accounts_for_ledger(ledger_id)

        assets = []
        liabilities = []
        equity = []
        income = []
        expenses = []

        for acc in accounts:
            entry = {"account_id": acc.id, "balance": acc.balance}

            if acc.code == AccountType.ASSET:
                assets.append(entry)
            elif acc.code == AccountType.LIABILITY:
                liabilities.append(entry)
            elif acc.code == AccountType.EQUITY:
                equity.append(entry)
            elif acc.code == AccountType.INCOME:
                income.append(entry)
            elif acc.code == AccountType.EXPENSE:
                expenses.append(entry)

        total_assets = sum(a["balance"] for a in assets)
        total_liabilities = sum(l["balance"] for l in liabilities)
        total_equity = sum(e["balance"] for e in equity)
        total_income = sum(i["balance"] for i in income)
        total_expenses = sum(e["balance"] for e in expenses)

        return {
            "ledger_id": ledger_id,
            "assets": {"accounts": assets, "total": total_assets},
            "liabilities": {"accounts": liabilities, "total": total_liabilities},
            "equity": {"accounts": equity, "total": total_equity},
            "income": {"accounts": income, "total": total_income},
            "expenses": {"accounts": expenses, "total": total_expenses},
            "balanced": total_assets == (total_liabilities + total_equity + total_income - total_expenses),
        }

    def general_ledger(self, ledger_id: str, account_id: str | None = None) -> list[dict]:
        """
        General ledger: all postings for a ledger, optionally filtered by account.
        Returns chronological list of postings with transfer details.
        """
        if account_id:
            posting_docs = (
                self.storage.postings
                .where(filter=FieldFilter("account_id", "==", account_id))
                .order_by("created_at")
                .stream()
            )
        else:
            posting_docs = (
                self.storage.postings
                .order_by("created_at")
                .stream()
            )

        entries = []
        for doc in posting_docs:
            data = doc.to_dict()
            posting = self.storage._deserialize_posting(data)

            # get transfer details
            transfer = self.storage.get_transfer(posting.transfer_id)
            if transfer and transfer.ledger_id != ledger_id:
                continue

            entries.append({
                "posting_id": posting.id,
                "transfer_id": posting.transfer_id,
                "account_id": posting.account_id,
                "type": posting.posting_type.value,
                "amount": posting.amount,
                "code": transfer.code.value if transfer else None,
                "user_data": transfer.user_data if transfer else None,
                "created_at": posting.created_at,
            })

        return entries

    def _get_accounts_for_ledger(self, ledger_id: str) -> list:
        docs = (
            self.storage.accounts
            .where(filter=FieldFilter("ledger_id", "==", ledger_id))
            .stream()
        )
        return [self.storage._deserialize_account(doc.to_dict()) for doc in docs]
