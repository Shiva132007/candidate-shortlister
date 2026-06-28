import os
import sqlite3
import hashlib
import uuid
from datetime import datetime, timedelta

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "auth.db")

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password_hash BLOB NOT NULL,
            salt BLOB NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create sessions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            FOREIGN KEY (username) REFERENCES users(username) ON DELETE CASCADE
        )
    """)
    
    conn.commit()
    conn.close()

def hash_password(password: str, salt: bytes = None) -> tuple[bytes, bytes]:
    if salt is None:
        salt = os.urandom(16)
    # Using 100,000 iterations of PBKDF2 with SHA-256
    pwd_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
    return pwd_hash, salt

def register_user(username: str, password: str) -> bool:
    username = username.strip().lower()
    if not username or not password:
        return False
    
    pwd_hash, salt = hash_password(password)
    
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (username, password_hash, salt) VALUES (?, ?, ?)",
            (username, pwd_hash, salt)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        # Username already exists
        return False
    finally:
        conn.close()

def authenticate_user(username: str, password: str) -> bool:
    username = username.strip().lower()
    if not username or not password:
        return False
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT password_hash, salt FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return False
        
    db_hash = row["password_hash"]
    salt = row["salt"]
    
    pwd_hash, _ = hash_password(password, salt)
    return pwd_hash == db_hash

def create_session(username: str, days_valid: int = 7) -> str:
    username = username.strip().lower()
    token = uuid.uuid4().hex
    expires_at = datetime.utcnow() + timedelta(days=days_valid)
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO sessions (token, username, expires_at) VALUES (?, ?, ?)",
        (token, username, expires_at.isoformat())
    )
    conn.commit()
    conn.close()
    return token

def verify_session(token: str) -> str | None:
    if not token:
        return None
        
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT username, expires_at FROM sessions WHERE token = ?", (token,))
    row = cursor.fetchone()
    
    if not row:
        conn.close()
        return None
        
    expires_at = datetime.fromisoformat(row["expires_at"])
    if expires_at < datetime.utcnow():
        # Session expired, clean it up
        cursor.execute("DELETE FROM sessions WHERE token = ?", (token,))
        conn.commit()
        conn.close()
        return None
        
    conn.close()
    return row["username"]

def destroy_session(token: str):
    if not token:
        return
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sessions WHERE token = ?", (token,))
    conn.commit()
    conn.close()
