# db/database.py — Omega Claw SQLite Layer
import sqlite3
import os
import logging
from datetime import datetime
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

DB_PATH = os.path.expanduser(os.getenv("OMEGA_CLAW_DB", "~/.omega-claw/omega_claw.db"))
DB_KEY = os.getenv("OMEGA_CLAW_DB_KEY")

_fernet = None
if DB_KEY:
    try:
        _fernet = Fernet(DB_KEY.encode('utf-8'))
    except ValueError as e:
        logger.error(f"Invalid OMEGA_CLAW_DB_KEY: {e}. Ensure it is a valid 32-byte base64 string.")

if not _fernet:
    logger.warning("OMEGA_CLAW_DB_KEY is missing or invalid! Database contents will be stored in PLAINTEXT.")


def encrypt_val(val: str) -> str:
    if not val or not _fernet: return val
    return _fernet.encrypt(val.encode('utf-8')).decode('utf-8')


def decrypt_val(val: str) -> str:
    if not val or not _fernet: return val
    try:
        return _fernet.decrypt(val.encode('utf-8')).decode('utf-8')
    except Exception:
        # Fallback for plaintext (seamless migration)
        return val


def _ensure_dir():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


def get_connection():
    _ensure_dir()
    db_exists = os.path.exists(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # SECURITY §4.5: Restrict DB file permissions to owner-only
    if not db_exists:
        os.chmod(DB_PATH, 0o600)
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS jobs (
            id          TEXT PRIMARY KEY,
            name        TEXT,
            kit         TEXT,
            mode        TEXT,
            status      TEXT DEFAULT 'PENDING',
            created_at  DATETIME,
            completed_at DATETIME,
            summary     TEXT
        );

        CREATE TABLE IF NOT EXISTS command_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER,
            message     TEXT,
            intent      TEXT,
            response    TEXT,
            timestamp   DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS user_wizard_state (
            user_id     INTEGER PRIMARY KEY,
            state       TEXT
        );

        CREATE TABLE IF NOT EXISTS user_autonomy_state (
            user_id     INTEGER PRIMARY KEY,
            mode        TEXT DEFAULT 'security'
        );
    """)
    conn.commit()
    conn.close()


def log_command(user_id: int, message: str, intent: str, response: str):
    conn = get_connection()
    conn.execute(
        "INSERT INTO command_log (user_id, message, intent, response) VALUES (?, ?, ?, ?)",
        (user_id, encrypt_val(message), encrypt_val(intent), encrypt_val(response))
    )
    conn.commit()
    conn.close()


def create_job(job_id: str, name: str, kit: str, mode: str):
    conn = get_connection()
    conn.execute(
        "INSERT INTO jobs (id, name, kit, mode, status, created_at) VALUES (?, ?, ?, ?, 'PENDING', ?)",
        (job_id, encrypt_val(name), kit, mode, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()


def update_job_status(job_id: str, status: str, summary: str = None):
    conn = get_connection()
    if status == "COMPLETE":
        conn.execute(
            "UPDATE jobs SET status = ?, summary = ?, completed_at = ? WHERE id = ?",
            (status, encrypt_val(summary), datetime.now().isoformat(), job_id)
        )
    else:
        conn.execute("UPDATE jobs SET status = ? WHERE id = ?", (status, job_id))
    conn.commit()
    conn.close()


def get_all_jobs():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM jobs ORDER BY created_at DESC").fetchall()
    conn.close()
    
    decrypted = []
    for r in rows:
        d = dict(r)
        d['name'] = decrypt_val(d.get('name', '')) if d.get('name') else d.get('name')
        d['summary'] = decrypt_val(d.get('summary', '')) if d.get('summary') else d.get('summary')
        decrypted.append(d)
    return decrypted


def get_recent_commands(limit=10):
    conn = get_connection()
    rows = conn.execute("SELECT * FROM command_log ORDER BY timestamp DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    
    decrypted = []
    for r in rows:
        d = dict(r)
        d['message'] = decrypt_val(d.get('message', '')) if d.get('message') else d.get('message')
        d['intent'] = decrypt_val(d.get('intent', '')) if d.get('intent') else d.get('intent')
        d['response'] = decrypt_val(d.get('response', '')) if d.get('response') else d.get('response')
        decrypted.append(d)
    return decrypted


def get_wizard_state(user_id: int) -> dict:
    import json
    conn = get_connection()
    row = conn.execute("SELECT state FROM user_wizard_state WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    if row and row['state']:
        try:
            return json.loads(decrypt_val(row['state']))
        except:
            pass
    return {}


def set_wizard_state(user_id: int, state: dict):
    import json
    conn = get_connection()
    enc_state = encrypt_val(json.dumps(state))
    conn.execute(
        "INSERT INTO user_wizard_state (user_id, state) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET state=excluded.state",
        (user_id, enc_state)
    )
    conn.commit()
    conn.close()


def clear_wizard_state(user_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM user_wizard_state WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def get_autonomy_mode(user_id: int) -> str:
    conn = get_connection()
    row = conn.execute("SELECT mode FROM user_autonomy_state WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    if row and row['mode']:
        return decrypt_val(row['mode'])
    return "security"  # Default mode


def set_autonomy_mode(user_id: int, mode: str):
    conn = get_connection()
    enc_mode = encrypt_val(mode)
    conn.execute(
        "INSERT INTO user_autonomy_state (user_id, mode) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET mode=excluded.mode",
        (user_id, enc_mode)
    )
    conn.commit()
    conn.close()
