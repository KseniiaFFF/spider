import sqlite3
import logging

from threading import Lock
from datetime import timedelta, datetime

DB_PATH = "market_orders.db"
db_lock = Lock()
logger = logging.getLogger(__name__)

def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS pending_signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_name TEXT NOT NULL,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,           -- BUY / SELL
            qty REAL NOT NULL,
            activate_price REAL NOT NULL,
            stop_loss REAL NOT NULL,
            take_profit REAL NOT NULL,
            created_at TEXT NOT NULL,
            end_monitor TEXT NOT NULL,
            status TEXT DEFAULT 'PENDING' CHECK(status IN ('PENDING', 'DONE', 'EXPIRED', 'ERROR'))
        )
    """)
    conn.commit()
    conn.close()


def pending_signal_exists(account_name: str, symbol: str):

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT 1
        FROM pending_signals
        WHERE account_name = ?
        AND symbol = ?
        AND status = 'PENDING'
        LIMIT 1
    """, (account_name, symbol))

    exists = cur.fetchone() is not None

    conn.close()

    return exists


def save_pending_signal(account_name, symbol, side, qty, activate_price, sl, tp, duration_hours=5):

    if pending_signal_exists(account_name, symbol):
        logger.info(
            f"Уже существует PENDING сигнал "
            f"{account_name} {symbol}"
        )
        return False

    with db_lock:

        conn = get_conn()
        cur = conn.cursor()
        created = datetime.now().isoformat()
        end_mon = (datetime.now() + timedelta(hours=duration_hours)).isoformat()
        
        cur.execute("""
            INSERT INTO pending_signals 
            (account_name, symbol, side, qty, activate_price, stop_loss, take_profit, created_at, end_monitor, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING')
        """, (account_name, symbol, side, qty, activate_price, sl, tp, created, end_mon))
        conn.commit()
        conn.close()


def get_pending_signals():

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM pending_signals 
        WHERE status = 'PENDING'
    """)
    rows = cur.fetchall()
    conn.close()
    return rows


def update_signal_status(sig_id: int, new_status: str):

    """new_status: 'DONE', 'EXPIRED', 'ERROR'"""
    if new_status not in ('DONE', 'EXPIRED', 'ERROR'):
        return False
    
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        UPDATE pending_signals 
        SET status = ? 
        WHERE id = ?
    """, (new_status, sig_id))
    conn.commit()
    conn.close()
    return True


def cleanup_expired_signals():

    """Переводит просроченные сигналы в статус EXPIRED"""
    now = datetime.now().isoformat()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        UPDATE pending_signals 
        SET status = 'EXPIRED' 
        WHERE end_monitor < ? AND status = 'PENDING'
    """, (now,))
    updated = cur.rowcount
    conn.commit()
    conn.close()
    if updated > 0:
        logger.info(f"Истекло {updated} pending сигналов")
    return updated