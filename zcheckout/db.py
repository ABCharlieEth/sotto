import os, sqlite3, threading
from . import config

_lock = threading.Lock()
SCHEMA = """
CREATE TABLE IF NOT EXISTS merchants (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, key_hash TEXT NOT NULL, address TEXT NOT NULL,
  webhook TEXT, created INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS invoices (
  id TEXT PRIMARY KEY, merchant_id TEXT NOT NULL REFERENCES merchants(id), label TEXT, order_ref TEXT,
  amount_zat INTEGER NOT NULL, address TEXT NOT NULL, memo TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'open',          -- open, seen, paid, expired, underpaid
  received_zat INTEGER NOT NULL DEFAULT 0, txid TEXT, mined_height INTEGER, confirmations INTEGER DEFAULT 0,
  created INTEGER NOT NULL, expires INTEGER NOT NULL, paid_at INTEGER, webhook_sent INTEGER DEFAULT 0);
CREATE INDEX IF NOT EXISTS inv_merchant ON invoices(merchant_id, created);
CREATE TABLE IF NOT EXISTS seen_outputs (txid TEXT, pool INTEGER, idx INTEGER, invoice_id TEXT, PRIMARY KEY (txid, pool, idx));
"""

def conn():
    os.makedirs(config.DATA, exist_ok=True)
    c = sqlite3.connect(os.path.join(config.DATA, "app.sqlite"), timeout=10, check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL"); c.execute("PRAGMA foreign_keys=ON")
    return c

_c = None
def db():
    global _c
    if _c is None:
        _c = conn(); _c.executescript(SCHEMA)
    return _c

def q(sql, args=(), one=False):
    with _lock:
        cur = db().execute(sql, args); rows = cur.fetchall()
    return (rows[0] if rows else None) if one else rows

def x(sql, args=()):
    with _lock:
        c = db(); c.execute(sql, args); c.commit()
