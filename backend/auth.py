"""Authentication module for LLM Council (OWASP hardened).

Features:
- Constant-time password and token verification (hmac.compare_digest)
- HMAC-SHA256 signed tamper-evident session tokens (no external heavy dependencies)
- Fail-closed exception handling
- Configurable via ADMIN_USERNAME, ADMIN_PASSWORD, and JWT_SECRET
"""

import os
import time
import hmac
import hashlib
import base64
import json
from typing import Optional, Dict, Any

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")
# No committed fallback: a published default key lets anyone forge tokens.
JWT_SECRET = os.getenv("JWT_SECRET", "")
TOKEN_TTL_SECONDS = int(os.getenv("TOKEN_TTL_SECONDS", str(7 * 24 * 3600)))  # 7 days


def _signing_key() -> bytes:
    """Return the HMAC key, failing loudly when it is not configured."""
    if not JWT_SECRET:
        raise RuntimeError("JWT_SECRET is not set; refusing to sign or verify tokens")
    return JWT_SECRET.encode("utf-8")


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64decode(s: str) -> bytes:
    padding = 4 - (len(s) % 4)
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s.encode("utf-8"))


def create_token(username: str) -> str:
    """Create an HMAC-SHA256 signed session token."""
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": username,
        "iat": int(time.time()),
        "exp": int(time.time()) + TOKEN_TTL_SECONDS,
    }
    
    encoded_header = _b64encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    encoded_payload = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    
    signing_input = f"{encoded_header}.{encoded_payload}".encode("utf-8")
    signature = hmac.new(_signing_key(), signing_input, hashlib.sha256).digest()
    encoded_sig = _b64encode(signature)
    
    return f"{encoded_header}.{encoded_payload}.{encoded_sig}"


AUTH_CONFIG_FILE = os.getenv("AUTH_CONFIG_FILE", os.path.join(os.getenv("DATA_DIR", "data"), "auth_config.json"))


def _load_auth_config() -> Optional[Dict[str, Any]]:
    """Load persistent credentials config if present."""
    if os.path.exists(AUTH_CONFIG_FILE):
        try:
            with open(AUTH_CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None


def _save_auth_config(data: Dict[str, Any]) -> bool:
    """Save persistent credentials config atomically."""
    try:
        os.makedirs(os.path.dirname(AUTH_CONFIG_FILE), exist_ok=True)
        temp_file = f"{AUTH_CONFIG_FILE}.tmp.{os.getpid()}"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(temp_file, AUTH_CONFIG_FILE)
        return True
    except Exception:
        return False


def hash_password(password: str, salt: Optional[bytes] = None) -> tuple[str, str]:
    """Derive PBKDF2-HMAC-SHA256 key with 100k iterations."""
    if salt is None:
        salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
    return base64.b64encode(dk).decode("utf-8"), base64.b64encode(salt).decode("utf-8")


def verify_password_hash(password: str, stored_hash: str, stored_salt: str) -> bool:
    """Verify password against stored PBKDF2 hash using constant-time comparison."""
    try:
        salt = base64.b64decode(stored_salt.encode("utf-8"))
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
        calc_hash = base64.b64encode(dk).decode("utf-8")
        return hmac.compare_digest(calc_hash, stored_hash)
    except Exception:
        return False


def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify token signature and expiry with constant-time compare. Fail-closed on error."""
    if not token or not isinstance(token, str) or "." not in token:
        return None
        
    parts = token.strip().split(".")
    if len(parts) != 3:
        return None
        
    encoded_header, encoded_payload, encoded_sig = parts
    try:
        signing_input = f"{encoded_header}.{encoded_payload}".encode("utf-8")
        expected_sig = hmac.new(_signing_key(), signing_input, hashlib.sha256).digest()
        actual_sig = _b64decode(encoded_sig)
        
        # Constant-time comparison prevents timing attacks
        if not hmac.compare_digest(expected_sig, actual_sig):
            return None
            
        payload = json.loads(_b64decode(encoded_payload).decode("utf-8"))
        if payload.get("exp", 0) < time.time():
            return None
            
        return payload
    except Exception:
        # Fail closed on any tampering or decoding exception
        return None


def verify_credentials(username: str, password: str) -> bool:
    """Verify username and password with constant-time comparison against configured credentials."""
    if not username or not password:
        return False
        
    cfg = _load_auth_config()
    if cfg and "password_hash" in cfg and "salt" in cfg:
        stored_user = cfg.get("username", ADMIN_USERNAME)
        user_ok = hmac.compare_digest(username.strip().encode("utf-8"), stored_user.encode("utf-8"))
        pass_ok = verify_password_hash(password, cfg["password_hash"], cfg["salt"])
        return user_ok and pass_ok

    user_ok = hmac.compare_digest(username.strip().encode("utf-8"), ADMIN_USERNAME.encode("utf-8"))
    pass_ok = hmac.compare_digest(password.encode("utf-8"), ADMIN_PASSWORD.encode("utf-8"))
    return user_ok and pass_ok


def change_password(username: str, old_password: str, new_password: str) -> bool:
    """Change user password after verifying existing credentials."""
    if not verify_credentials(username, old_password):
        return False
    if len(new_password) < 6:
        raise ValueError("Password must be at least 6 characters long")
    p_hash, salt = hash_password(new_password)
    return _save_auth_config({
        "username": username.strip(),
        "password_hash": p_hash,
        "salt": salt,
        "updated_at": int(time.time()),
    })


def is_default_password() -> bool:
    """Check if the system is currently using uncustomized default password."""
    cfg = _load_auth_config()
    if cfg:
        return False
    return ADMIN_PASSWORD == "admin"


def is_auth_required() -> bool:
    """Return whether authentication is strictly enforced on the server."""
    return os.getenv("AUTH_ENABLED", "true").lower() in ("true", "1", "yes")


def check_auth_header(authorization: Optional[str]) -> bool:
    """Validate Authorization header if auth is required."""
    if not is_auth_required():
        return True
    if not authorization or not authorization.startswith("Bearer "):
        return False
    token = authorization[7:].strip()
    return verify_token(token) is not None


