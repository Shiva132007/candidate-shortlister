import os
import hashlib
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False


class SupabaseUserStore:
    """
    Supabase PostgreSQL integration for user management.
    Handles:
      - User registration and login (with password hashing)
      - Session token management
      - User activity tracking (logins, searches, rankings, etc.)

    Falls back gracefully to SQLite (auth_db.py) if env vars not set.
    """

    def __init__(self):
        self.client: Optional[Client] = None

        if SUPABASE_AVAILABLE:
            url = os.environ.get("SUPABASE_URL", "").strip()
            key = os.environ.get("SUPABASE_KEY", "").strip()
            if url and key:
                self.client = create_client(url, key)
                print(f"Supabase: Connected to project at {url}")
            else:
                print("Supabase: No credentials set — using SQLite fallback")

    def is_available(self) -> bool:
        return SUPABASE_AVAILABLE and self.client is not None

    # ─── Password Utilities ─────────────────────────────────────────────────

    def _hash_password(self, password: str, salt: Optional[str] = None) -> tuple[str, str]:
        """Hash a password with PBKDF2-HMAC-SHA256 and return (hash_hex, salt_hex)."""
        if salt is None:
            salt = os.urandom(32).hex()
        key = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 260000)
        return key.hex(), salt

    def _verify_password(self, password: str, stored_hash: str, salt: str) -> bool:
        key, _ = self._hash_password(password, salt)
        return key == stored_hash

    # ─── User Registration ──────────────────────────────────────────────────

    def register_user(self, username: str, password: str) -> Dict[str, Any]:
        """Register a new user. Returns {'success': bool, 'detail': str, 'token': str|None}"""
        if not self.is_available():
            return {"success": False, "detail": "Supabase not configured"}

        try:
            # Check if username already exists
            existing = self.client.table("users").select("username").eq("username", username).execute()
            if existing.data:
                return {"success": False, "detail": "Username already exists"}

            # Hash password
            pwd_hash, salt = self._hash_password(password)

            # Insert user
            self.client.table("users").insert({
                "username": username,
                "password_hash": pwd_hash,
                "salt": salt,
                "created_at": datetime.utcnow().isoformat()
            }).execute()

            # Auto login — create session token
            token = self._create_session(username)

            # Log registration activity
            self.log_activity(username, "register", metadata={"ip": "unknown"})

            return {"success": True, "token": token, "username": username}

        except Exception as e:
            return {"success": False, "detail": str(e)}

    # ─── User Login ─────────────────────────────────────────────────────────

    def login_user(self, username: str, password: str) -> Dict[str, Any]:
        """Login a user. Returns {'success': bool, 'token': str|None, 'detail': str}"""
        if not self.is_available():
            return {"success": False, "detail": "Supabase not configured"}

        try:
            result = self.client.table("users").select("*").eq("username", username).execute()
            if not result.data:
                return {"success": False, "detail": "Invalid username or password"}

            user = result.data[0]
            if not self._verify_password(password, user["password_hash"], user["salt"]):
                return {"success": False, "detail": "Invalid username or password"}

            token = self._create_session(username)
            self.log_activity(username, "login")

            return {"success": True, "token": token, "username": username}

        except Exception as e:
            return {"success": False, "detail": str(e)}

    # ─── Session Management ─────────────────────────────────────────────────

    def _create_session(self, username: str, expires_hours: int = 72) -> str:
        """Create a session token and store in Supabase sessions table."""
        token = str(uuid.uuid4())
        expires_at = (datetime.utcnow() + timedelta(hours=expires_hours)).isoformat()
        self.client.table("sessions").insert({
            "token": token,
            "username": username,
            "expires_at": expires_at
        }).execute()
        return token

    def verify_session(self, token: str) -> Optional[str]:
        """Verify a session token. Returns username if valid, None if expired/invalid."""
        if not self.is_available() or not token:
            return None

        try:
            result = self.client.table("sessions").select("*").eq("token", token).execute()
            if not result.data:
                return None

            session = result.data[0]
            expires_at_str = session["expires_at"]

            # Parse timezone-aware datetime from Supabase (timestamptz)
            expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
            now = datetime.now(expires_at.tzinfo)  # Compare in same timezone

            if expires_at < now:
                self.destroy_session(token)
                return None

            return session["username"]
        except Exception as e:
            print(f"Session verify warning: {e}")
            return None

    def destroy_session(self, token: str):
        """Invalidate a session token on logout."""
        if not self.is_available() or not token:
            return
        try:
            self.client.table("sessions").delete().eq("token", token).execute()
        except Exception:
            pass

    # ─── Activity Tracking ──────────────────────────────────────────────────

    def log_activity(self, username: str, action: str, role_id: str = "default", metadata: Dict = None):
        """
        Log user activity to Supabase.
        Actions: 'register', 'login', 'logout', 'rank_candidates',
                 'upload_candidates', 'set_jd', 'ai_chat', 'compare', 'export'
        """
        if not self.is_available():
            return
        try:
            self.client.table("user_activity").insert({
                "username": username,
                "action": action,
                "role_id": role_id,
                "metadata": metadata or {},
                "timestamp": datetime.utcnow().isoformat()
            }).execute()
        except Exception as e:
            print(f"Activity log warning: {e}")

    def get_user_activity(self, username: str, limit: int = 50) -> list:
        """Retrieve recent activity for a user."""
        if not self.is_available():
            return []
        try:
            result = (
                self.client.table("user_activity")
                .select("*")
                .eq("username", username)
                .order("timestamp", desc=True)
                .limit(limit)
                .execute()
            )
            return result.data or []
        except Exception:
            return []

    def get_all_users(self) -> list:
        """Retrieve all registered users (admin overview)."""
        if not self.is_available():
            return []
        try:
            result = self.client.table("users").select("username, created_at").order("created_at", desc=True).execute()
            return result.data or []
        except Exception:
            return []
