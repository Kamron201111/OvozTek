
import sqlite3

DB = "votes.db"

def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS votes(phone TEXT, date TEXT)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_phone ON votes(phone)")
    conn.commit()
    conn.close()

def add_votes(votes):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.executemany("INSERT INTO votes(phone,date) VALUES(?,?)", votes)
    conn.commit()
    conn.close()

def search_phone(last_digits):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    q = f"%{last_digits}"
    c.execute("SELECT phone,date FROM votes WHERE phone LIKE ?", (q,))
    res = c.fetchone()
    conn.close()
    return res

def count_votes():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM votes")
    r = c.fetchone()[0]
    conn.close()
    return r

def get_all_votes():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT phone,date FROM votes")
    data = c.fetchall()
    conn.close()
    return data
