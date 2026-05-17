from pathlib import Path

MIGRATIONS_DIR = Path(__file__).parent


def run_migrations(conn):
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        cur.execute("SELECT version FROM schema_migrations")
        applied = {row[0] for row in cur.fetchall()}

        sql_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
        for sql_file in sql_files:
            version = sql_file.stem
            if version not in applied:
                sql = sql_file.read_text()
                cur.execute(sql)
                cur.execute(
                    "INSERT INTO schema_migrations (version) VALUES (%s)",
                    (version,),
                )
