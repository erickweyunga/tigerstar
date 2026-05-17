CREATE TABLE IF NOT EXISTS ledgers (
    id TEXT PRIMARY KEY,
    currency TEXT NOT NULL,
    precision_ INTEGER NOT NULL DEFAULT 2,
    max_transfer_amount BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS accounts (
    id TEXT PRIMARY KEY,
    ledger_id TEXT NOT NULL REFERENCES ledgers(id),
    code TEXT NOT NULL,
    debits_pending BIGINT NOT NULL DEFAULT 0,
    debits_posted BIGINT NOT NULL DEFAULT 0,
    credits_pending BIGINT NOT NULL DEFAULT 0,
    credits_posted BIGINT NOT NULL DEFAULT 0,
    flag_debits_must_not_exceed_credits BOOLEAN NOT NULL DEFAULT FALSE,
    flag_credits_must_not_exceed_debits BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT positive_balances CHECK (
        debits_pending >= 0 AND debits_posted >= 0
        AND credits_pending >= 0 AND credits_posted >= 0
    )
);

CREATE TABLE IF NOT EXISTS transfers (
    id TEXT PRIMARY KEY,
    debit_account_id TEXT NOT NULL REFERENCES accounts(id),
    credit_account_id TEXT NOT NULL REFERENCES accounts(id),
    ledger_id TEXT NOT NULL REFERENCES ledgers(id),
    amount BIGINT NOT NULL,
    code TEXT NOT NULL,
    flag_linked BOOLEAN NOT NULL DEFAULT FALSE,
    flag_pending BOOLEAN NOT NULL DEFAULT FALSE,
    flag_post_pending_transfer BOOLEAN NOT NULL DEFAULT FALSE,
    flag_void_pending_transfer BOOLEAN NOT NULL DEFAULT FALSE,
    pending_id TEXT,
    user_data TEXT,
    timeout INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT positive_amount CHECK (amount > 0),
    CONSTRAINT different_accounts CHECK (debit_account_id != credit_account_id)
);

CREATE TABLE IF NOT EXISTS postings (
    id TEXT PRIMARY KEY,
    transfer_id TEXT NOT NULL REFERENCES transfers(id),
    account_id TEXT NOT NULL REFERENCES accounts(id),
    posting_type TEXT NOT NULL,
    amount BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT positive_posting_amount CHECK (amount > 0)
);

-- indexes
CREATE INDEX IF NOT EXISTS idx_accounts_ledger ON accounts(ledger_id);

CREATE INDEX IF NOT EXISTS idx_transfers_ledger ON transfers(ledger_id, created_at DESC)
    INCLUDE (debit_account_id, credit_account_id, amount, code);

CREATE INDEX IF NOT EXISTS idx_transfers_pending ON transfers(created_at)
    WHERE flag_pending = TRUE;

CREATE INDEX IF NOT EXISTS idx_postings_account ON postings(account_id, created_at DESC)
    INCLUDE (posting_type, amount);

CREATE INDEX IF NOT EXISTS idx_postings_transfer ON postings(transfer_id)
    INCLUDE (account_id, posting_type, amount);

