import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from src.storage.base import StorageBase
from src.ledgers.model import Ledger
from src.accounts.model import Account
from src.transfers.model import Transfer
from src.transfers.posting import Posting
from src.core.types import AccountType, AccountFlags, TransferCode, TransferFlags, PostingType
from src.core.exceptions import AccountNotFound


class FirestoreStorage(StorageBase):

    def __init__(self, credentials_path: str, database_id: str = "default"):
        if not firebase_admin._apps:
            cred = credentials.Certificate(credentials_path)
            firebase_admin.initialize_app(cred)

        self.db = firestore.client(database_id=database_id)

    @property
    def _ledgers(self):
        return self.db.collection("ledgers")

    @property
    def _accounts(self):
        return self.db.collection("accounts")

    @property
    def _transfers(self):
        return self.db.collection("transfers")

    @property
    def _postings(self):
        return self.db.collection("postings")

    # --- interface ---

    def save_ledger(self, ledger: Ledger):
        self._ledgers.document(ledger.id).set(self._serialize_ledger(ledger))

    def get_ledger(self, ledger_id: str) -> Ledger | None:
        doc = self._ledgers.document(ledger_id).get()
        if not doc.exists:
            return None
        return self._deserialize_ledger(doc.to_dict())

    def save_account(self, account: Account):
        self._accounts.document(account.id).set(self._serialize_account(account))

    def save_accounts_batch(self, accounts: list[Account]):
        batch = self.db.batch()
        for account in accounts:
            ref = self._accounts.document(account.id)
            batch.set(ref, self._serialize_account(account))
        batch.commit()

    def get_account(self, account_id: str) -> Account | None:
        doc = self._accounts.document(account_id).get()
        if not doc.exists:
            return None
        return self._deserialize_account(doc.to_dict())

    def get_accounts_batch(self, account_ids: list[str]) -> dict[str, Account]:
        if not account_ids:
            return {}
        refs = [self._accounts.document(aid) for aid in account_ids]
        docs = self.db.get_all(refs)
        result = {}
        for doc in docs:
            if doc.exists:
                result[doc.id] = self._deserialize_account(doc.to_dict())
        return result

    def save_transfer(self, transfer: Transfer):
        self._transfers.document(transfer.id).set(self._serialize_transfer(transfer))

    def get_transfer(self, transfer_id: str) -> Transfer | None:
        doc = self._transfers.document(transfer_id).get()
        if not doc.exists:
            return None
        return self._deserialize_transfer(doc.to_dict())

    def save_posting(self, posting: Posting):
        self._postings.document(posting.id).set(self._serialize_posting(posting))

    def get_postings_for_transfer(self, transfer_id: str) -> list[Posting]:
        docs = (
            self._postings
            .where(filter=FieldFilter("transfer_id", "==", transfer_id))
            .stream()
        )
        return [self._deserialize_posting(doc.to_dict()) for doc in docs]

    def execute_transfer(self, transfers, account_ids, pending_ids, process):
        transaction = self.db.transaction()

        @firestore.transactional
        def execute(transaction):
            pending_transfers = {}
            if pending_ids:
                refs = [self._transfers.document(pid) for pid in pending_ids]
                docs = self.db.get_all(refs, transaction=transaction)
                for doc in docs:
                    if not doc.exists:
                        raise ValueError("Pending transfer not found")
                    pt = self._deserialize_transfer(doc.to_dict())
                    pending_transfers[pt.id] = pt
                    account_ids.append(pt.debit_account_id)
                    account_ids.append(pt.credit_account_id)

            unique_ids = list(set(account_ids))
            account_refs = {aid: self._accounts.document(aid) for aid in unique_ids}
            accounts = {}
            if account_refs:
                docs = self.db.get_all(list(account_refs.values()), transaction=transaction)
                for doc in docs:
                    if not doc.exists:
                        raise AccountNotFound(doc.id)
                    accounts[doc.id] = self._deserialize_account(doc.to_dict())

            results, updated_accounts, postings = process(accounts, pending_transfers)

            for aid, account in updated_accounts.items():
                transaction.set(account_refs[aid], self._serialize_account(account))

            for result in results:
                transaction.set(
                    self._transfers.document(result.id),
                    self._serialize_transfer(result),
                )
            for posting in postings:
                transaction.set(
                    self._postings.document(posting.id),
                    self._serialize_posting(posting),
                )

            return results

        return execute(transaction)

    def query_accounts_by_ledger(self, ledger_id: str) -> list[Account]:
        docs = (
            self._accounts
            .where(filter=FieldFilter("ledger_id", "==", ledger_id))
            .stream()
        )
        return [self._deserialize_account(doc.to_dict()) for doc in docs]

    def query_transfers_by_ledger(self, ledger_id: str) -> list[Transfer]:
        docs = (
            self._transfers
            .where(filter=FieldFilter("ledger_id", "==", ledger_id))
            .order_by("created_at")
            .stream()
        )
        return [self._deserialize_transfer(doc.to_dict()) for doc in docs]

    def query_postings_by_account(self, account_id: str) -> list[Posting]:
        docs = (
            self._postings
            .where(filter=FieldFilter("account_id", "==", account_id))
            .order_by("created_at")
            .stream()
        )
        return [self._deserialize_posting(doc.to_dict()) for doc in docs]

    def query_postings_all(self) -> list[Posting]:
        docs = self._postings.order_by("created_at").stream()
        return [self._deserialize_posting(doc.to_dict()) for doc in docs]

    # --- serialization ---

    def _serialize_ledger(self, ledger: Ledger) -> dict:
        return {
            "id": ledger.id,
            "currency": ledger.currency,
            "precision": ledger.precision,
            "max_transfer_amount": ledger.max_transfer_amount,
            "created_at": ledger.created_at,
        }

    def _deserialize_ledger(self, data: dict) -> Ledger:
        return Ledger(
            id=data["id"],
            currency=data["currency"],
            precision=data.get("precision", 2),
            max_transfer_amount=data.get("max_transfer_amount"),
            created_at=data["created_at"],
        )

    def _serialize_account(self, account: Account) -> dict:
        return {
            "id": account.id,
            "ledger_id": account.ledger_id,
            "code": account.code.value,
            "debits_pending": account.debits_pending,
            "debits_posted": account.debits_posted,
            "credits_pending": account.credits_pending,
            "credits_posted": account.credits_posted,
            "flags": {
                "debits_must_not_exceed_credits": account.flags.debits_must_not_exceed_credits,
                "credits_must_not_exceed_debits": account.flags.credits_must_not_exceed_debits,
            },
            "created_at": account.created_at,
        }

    def _deserialize_account(self, data: dict) -> Account:
        return Account(
            id=data["id"],
            ledger_id=data["ledger_id"],
            code=AccountType(data["code"]),
            debits_pending=data.get("debits_pending", 0),
            debits_posted=data["debits_posted"],
            credits_pending=data.get("credits_pending", 0),
            credits_posted=data["credits_posted"],
            flags=AccountFlags(
                debits_must_not_exceed_credits=data["flags"]["debits_must_not_exceed_credits"],
                credits_must_not_exceed_debits=data["flags"]["credits_must_not_exceed_debits"],
            ),
            created_at=data["created_at"],
        )

    def _serialize_transfer(self, transfer: Transfer) -> dict:
        return {
            "id": transfer.id,
            "debit_account_id": transfer.debit_account_id,
            "credit_account_id": transfer.credit_account_id,
            "ledger_id": transfer.ledger_id,
            "amount": transfer.amount,
            "code": transfer.code.value,
            "flags": {
                "linked": transfer.flags.linked,
                "pending": transfer.flags.pending,
                "post_pending_transfer": transfer.flags.post_pending_transfer,
                "void_pending_transfer": transfer.flags.void_pending_transfer,
            },
            "pending_id": transfer.pending_id,
            "user_data": transfer.user_data,
            "timeout": transfer.timeout,
            "created_at": transfer.created_at,
        }

    def _deserialize_transfer(self, data: dict) -> Transfer:
        return Transfer(
            id=data["id"],
            debit_account_id=data["debit_account_id"],
            credit_account_id=data["credit_account_id"],
            ledger_id=data["ledger_id"],
            amount=data["amount"],
            code=TransferCode(data["code"]),
            flags=TransferFlags(
                linked=data["flags"].get("linked", False),
                pending=data["flags"].get("pending", False),
                post_pending_transfer=data["flags"].get("post_pending_transfer", False),
                void_pending_transfer=data["flags"].get("void_pending_transfer", False),
            ),
            pending_id=data.get("pending_id"),
            user_data=data.get("user_data"),
            timeout=data.get("timeout"),
            created_at=data["created_at"],
        )

    def _serialize_posting(self, posting: Posting) -> dict:
        return {
            "id": posting.id,
            "transfer_id": posting.transfer_id,
            "account_id": posting.account_id,
            "posting_type": posting.posting_type.value,
            "amount": posting.amount,
            "created_at": posting.created_at,
        }

    def _deserialize_posting(self, data: dict) -> Posting:
        return Posting(
            id=data["id"],
            transfer_id=data["transfer_id"],
            account_id=data["account_id"],
            posting_type=PostingType(data["posting_type"]),
            amount=data["amount"],
            created_at=data["created_at"],
        )
