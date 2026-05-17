import os
from dotenv import load_dotenv

from src import TigerStar, PostgresStorage
from src import Ledger, Account, AccountType, AccountFlags
from src import Transfer, TransferCode

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

storage = PostgresStorage(dsn=DATABASE_URL)
storage.migrate()

engine = TigerStar(storage=storage)

# create a ledger
ledger = Ledger(currency="TZS", precision=0, max_transfer_amount=10_000_000)
engine.create_ledger(ledger)

# create accounts
cash = Account(ledger_id=ledger.id, code=AccountType.ASSET)
user = Account(
    ledger_id=ledger.id,
    code=AccountType.LIABILITY,
    flags=AccountFlags(debits_must_not_exceed_credits=True),
)
engine.create_accounts([cash, user])

# deposit 50,000
engine.create_transfers([
    Transfer(
        debit_account_id=cash.id,
        credit_account_id=user.id,
        ledger_id=ledger.id,
        amount=50000,
        code=TransferCode.PAYMENT,
    ),
])

print(f"Ledger: {ledger.id}")
print(f"Cash account: {cash.id}")
print(f"User account: {user.id}")

# check balances
cash_account = storage.get_account(cash.id)
user_account = storage.get_account(user.id)
print(f"Cash debits_posted: {cash_account.debits_posted}")
print(f"User credits_posted: {user_account.credits_posted}")

storage.close()
