import sqlite3
import logging
from contextlib import contextmanager

logger = logging.getLogger(__name__)

DB = "votes.db"

@contextmanager
def get_conn():
    conn = sqlite3.connect(DB, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"DB xatolik: {e}")
        raise
    finally:
        conn.close()

def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS votes (
                id    INTEGER PRIMARY KEY AUTOINCREMENT,
                phone TEXT NOT NULL,
                date  TEXT,
                UNIQUE(phone, date)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_phone ON votes(phone)")
    logger.info("DB tayyor ✅")

def add_votes(votes: list[tuple]) -> int:
    """
    Bir odam bir xil sana bilan ikki marta saqlanmaydi.
    Lekin bir odam turli sanada ovoz bergan bo'lsa — hammasi saqlanadi.
    Qaytaradi: qo'shilgan yangi yozuvlar soni.
    """
    if not votes:
        return 0
    with get_conn() as conn:
        cur = conn.executemany(
            "INSERT OR IGNORE INTO votes(phone, date) VALUES(?, ?)",
            votes,
        )
        return cur.rowcount

def search_phone(last_digits: str) -> list[tuple]:
    """Oxirgi N raqam bo'yicha qidiradi. Maksimal 50 ta natija."""
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT phone, date FROM votes WHERE phone LIKE ? ORDER BY date DESC LIMIT 50",
            (f"%{last_digits}",),
        )
        return [(row["phone"], row["date"]) for row in cur.fetchall()]

def count_votes() -> int:
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) FROM votes").fetchone()[0]

def get_stats() -> dict:
    with get_conn() as conn:
        total  = conn.execute("SELECT COUNT(*) FROM votes").fetchone()[0]
        latest = conn.execute("SELECT MAX(date) FROM votes").fetchone()[0]
        oldest = conn.execute("SELECT MIN(date) FROM votes").fetchone()[0]
    return {"total": total, "latest": latest, "oldest": oldest}

def get_all_votes() -> list[tuple]:
    with get_conn() as conn:
        cur = conn.execute("SELECT phone, date FROM votes ORDER BY date DESC")
        return [(row["phone"], row["date"]) for row in cur.fetchall()]

def clear_votes():
    with get_conn() as conn:
        conn.execute("DELETE FROM votes")
    logger.info("Baza tozalandi.")
