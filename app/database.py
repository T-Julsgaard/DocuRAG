"""
User, auth and usage database.

SQLite with WAL mode for decent concurrent access. Stores users, per-day token
usage, per-day Ask quotas, and an event log that powers the admin dashboard.

Default limits live in config.py and are used when a user row has no override.
"""

import sqlite3
import hashlib
import secrets
from pathlib import Path
from datetime import date as date_type, datetime, timezone

from config import ASK_DAILY_LIMIT, ASK_INPUT_TOKEN_LIMIT, ASK_OUTPUT_TOKEN_LIMIT


def get_conn(db_path: Path):
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: Path):
    """Create tables if they don't exist, then apply idempotent migrations."""
    conn = get_conn(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            username           TEXT    UNIQUE NOT NULL COLLATE NOCASE,
            password_hash      TEXT    NOT NULL,
            daily_token_limit  INTEGER DEFAULT 1000000,
            is_admin           INTEGER DEFAULT 0,
            created_at         TEXT    DEFAULT (date('now'))
        );

        CREATE TABLE IF NOT EXISTS token_usage (
            user_id     INTEGER NOT NULL,
            date        TEXT    NOT NULL,
            tokens_used INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, date),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS ask_usage (
            user_id          INTEGER NOT NULL,
            date             TEXT    NOT NULL,
            question_count   INTEGER DEFAULT 0,
            last_question_at TEXT,
            tokens_input     INTEGER DEFAULT 0,
            tokens_output    INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, date),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS usage_logs (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
            event_type     TEXT    NOT NULL,
            username       TEXT,
            query          TEXT,
            response       TEXT,
            tokens_input   INTEGER DEFAULT 0,
            tokens_output  INTEGER DEFAULT 0
        );
    """)
    conn.commit()

    for stmt in [
        "ALTER TABLE users ADD COLUMN ask_daily_limit INTEGER",
        "ALTER TABLE users ADD COLUMN daily_input_limit INTEGER",
        "ALTER TABLE users ADD COLUMN daily_output_limit INTEGER",
    ]:
        try:
            conn.execute(stmt)
        except sqlite3.OperationalError:
            pass  # column already exists
    conn.commit()
    conn.close()


# --- Password hashing (PBKDF2-HMAC-SHA256) ---

def _hash(password: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000)
    return f"{salt}:{h.hex()}"


def _verify(password: str, stored: str) -> bool:
    try:
        salt, h = stored.split(":", 1)
        check = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000)
        return secrets.compare_digest(check.hex(), h)
    except Exception:
        return False


# --- User operations ---

def get_user(db_path: Path, username: str):
    conn = get_conn(db_path)
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return dict(row) if row else None


def authenticate(db_path: Path, username: str, password: str):
    user = get_user(db_path, username)
    if user and _verify(password, user["password_hash"]):
        return user
    return None


def create_user(db_path: Path, username: str, password: str,
                daily_token_limit: int = 1_000_000, is_admin: bool = False) -> None:
    conn = get_conn(db_path)
    conn.execute(
        "INSERT INTO users (username, password_hash, daily_token_limit, is_admin) VALUES (?, ?, ?, ?)",
        (username, _hash(password), daily_token_limit, 1 if is_admin else 0)
    )
    conn.commit()
    conn.close()


def delete_user(db_path: Path, username: str) -> None:
    conn = get_conn(db_path)
    conn.execute("DELETE FROM users WHERE username = ?", (username,))
    conn.commit()
    conn.close()


def update_limit(db_path: Path, username: str, new_limit: int) -> None:
    conn = get_conn(db_path)
    conn.execute("UPDATE users SET daily_token_limit = ? WHERE username = ?", (new_limit, username))
    conn.commit()
    conn.close()


def update_password(db_path: Path, username: str, new_password: str) -> None:
    conn = get_conn(db_path)
    conn.execute("UPDATE users SET password_hash = ? WHERE username = ?",
                 (_hash(new_password), username))
    conn.commit()
    conn.close()


def update_ask_daily_limit(db_path: Path, username: str, new_limit: int) -> None:
    conn = get_conn(db_path)
    conn.execute("UPDATE users SET ask_daily_limit = ? WHERE username = ?", (new_limit, username))
    conn.commit()
    conn.close()


# --- Search-mode token tracking ---

def get_today_usage(db_path: Path, user_id: int) -> int:
    conn = get_conn(db_path)
    row = conn.execute(
        "SELECT tokens_used FROM token_usage WHERE user_id = ? AND date = ?",
        (user_id, date_type.today().isoformat())
    ).fetchone()
    conn.close()
    return row["tokens_used"] if row else 0


def add_tokens(db_path: Path, user_id: int, tokens: int) -> None:
    if tokens <= 0:
        return
    conn = get_conn(db_path)
    conn.execute("""
        INSERT INTO token_usage (user_id, date, tokens_used) VALUES (?, ?, ?)
        ON CONFLICT(user_id, date)
        DO UPDATE SET tokens_used = tokens_used + excluded.tokens_used
    """, (user_id, date_type.today().isoformat(), tokens))
    conn.commit()
    conn.close()


# --- Ask-mode quota tracking ---

def get_ask_status(db_path: Path, user_id: int) -> dict:
    """Return today's Ask quota status, using per-user overrides or defaults."""
    conn = get_conn(db_path)

    user_row = conn.execute(
        "SELECT ask_daily_limit, daily_input_limit, daily_output_limit FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()
    daily_limit = user_row["ask_daily_limit"] if user_row and user_row["ask_daily_limit"] is not None else ASK_DAILY_LIMIT
    daily_input_limit = user_row["daily_input_limit"] if user_row and user_row["daily_input_limit"] is not None else ASK_INPUT_TOKEN_LIMIT
    daily_output_limit = user_row["daily_output_limit"] if user_row and user_row["daily_output_limit"] is not None else ASK_OUTPUT_TOKEN_LIMIT

    today = date_type.today().isoformat()
    row = conn.execute(
        "SELECT question_count, tokens_input, tokens_output FROM ask_usage WHERE user_id = ? AND date = ?",
        (user_id, today)
    ).fetchone()
    conn.close()

    count = row["question_count"] if row else 0
    tokens_in_today = row["tokens_input"] if row else 0
    tokens_out_today = row["tokens_output"] if row else 0

    can_ask = (
        count < daily_limit
        and tokens_in_today < daily_input_limit
        and tokens_out_today < daily_output_limit
    )

    return {
        "count": count,
        "remaining": max(0, daily_limit - count),
        "daily_limit": daily_limit,
        "seconds_until_next": 0,
        "can_ask": can_ask,
        "tokens_in_today": tokens_in_today,
        "tokens_out_today": tokens_out_today,
        "daily_input_limit": daily_input_limit,
        "daily_output_limit": daily_output_limit,
    }


def record_ask_question(db_path: Path, user_id: int) -> None:
    """Increment the question counter. Call AFTER the status check passes."""
    conn = get_conn(db_path)
    today = date_type.today().isoformat()
    now_str = datetime.now(timezone.utc).isoformat()
    conn.execute("""
        INSERT INTO ask_usage (user_id, date, question_count, last_question_at)
        VALUES (?, ?, 1, ?)
        ON CONFLICT(user_id, date)
        DO UPDATE SET
            question_count   = question_count + 1,
            last_question_at = excluded.last_question_at
    """, (user_id, today, now_str))
    conn.commit()
    conn.close()


def add_ask_tokens(db_path: Path, user_id: int, tokens_input: int, tokens_output: int) -> None:
    if tokens_input <= 0 and tokens_output <= 0:
        return
    conn = get_conn(db_path)
    today = date_type.today().isoformat()
    conn.execute("""
        INSERT INTO ask_usage (user_id, date, question_count, tokens_input, tokens_output)
        VALUES (?, ?, 0, ?, ?)
        ON CONFLICT(user_id, date)
        DO UPDATE SET
            tokens_input  = tokens_input  + excluded.tokens_input,
            tokens_output = tokens_output + excluded.tokens_output
    """, (user_id, today, max(0, tokens_input), max(0, tokens_output)))
    conn.commit()
    conn.close()


# --- Event logging + dashboard ---

def log_event(db_path: Path, event_type: str, *, username: str | None = None,
              query: str | None = None, response: str | None = None,
              tokens_input: int = 0, tokens_output: int = 0) -> None:
    conn = get_conn(db_path)
    conn.execute(
        """INSERT INTO usage_logs (event_type, username, query, response, tokens_input, tokens_output)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (event_type, username, query, response, tokens_input, tokens_output)
    )
    conn.commit()
    conn.close()


def get_dashboard_data(db_path: Path, days: int = 30) -> dict:
    conn = get_conn(db_path)
    since = f"-{days} days"

    daily = conn.execute("""
        SELECT date(timestamp) AS day, event_type, COUNT(*) AS count
        FROM usage_logs
        WHERE timestamp >= datetime('now', ?)
        GROUP BY day, event_type
        ORDER BY day ASC
    """, (since,)).fetchall()

    searches = conn.execute("""
        SELECT timestamp, username, query
        FROM usage_logs
        WHERE event_type = 'search'
        ORDER BY timestamp DESC
        LIMIT 200
    """).fetchall()

    asks = conn.execute("""
        SELECT timestamp, username, query, response, tokens_input, tokens_output
        FROM usage_logs
        WHERE event_type = 'ask'
        ORDER BY timestamp DESC
        LIMIT 100
    """).fetchall()

    totals = conn.execute("""
        SELECT event_type, COUNT(*) AS count
        FROM usage_logs
        GROUP BY event_type
    """).fetchall()

    tok = conn.execute(
        "SELECT COALESCE(SUM(tokens_input + tokens_output), 0) AS t FROM usage_logs"
    ).fetchone()

    conn.close()
    return {
        "daily": [dict(r) for r in daily],
        "searches": [dict(r) for r in searches],
        "asks": [dict(r) for r in asks],
        "totals": {r["event_type"]: r["count"] for r in totals},
        "total_tokens": tok["t"] if tok else 0,
    }


def all_users_with_usage(db_path: Path):
    """All users with today's token usage joined in."""
    conn = get_conn(db_path)
    today = date_type.today().isoformat()
    rows = conn.execute("""
        SELECT
            u.id, u.username, u.daily_token_limit, u.is_admin, u.created_at,
            COALESCE(t.tokens_used, 0) AS tokens_today
        FROM users u
        LEFT JOIN token_usage t ON u.id = t.user_id AND t.date = ?
        ORDER BY u.username
    """, (today,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]
