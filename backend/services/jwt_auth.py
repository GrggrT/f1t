"""JWT token auth for launcher clients."""
import base64
import hashlib
import hmac
import json
import os
import time
import warnings

DEFAULT_SECRET = "INSECURE-DEV-ONLY-CHANGE-ME"
_warned_missing_secret = False


def get_jwt_secret() -> str:
    global _warned_missing_secret

    secret = os.getenv("NEXTAUTH_SECRET", "")
    if secret:
        return secret
    if not _warned_missing_secret:
        warnings.warn("NEXTAUTH_SECRET not set! JWT tokens will be insecure.", stacklevel=2)
        _warned_missing_secret = True
    return DEFAULT_SECRET

def create_token(user_id: int, days: int = 30) -> str:
    """Create a simple HMAC-signed JWT-like token."""
    header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).decode().rstrip("=")
    payload_data = {
        "sub": str(user_id),
        "exp": int(time.time()) + days * 86400,
        "iat": int(time.time()),
    }
    payload = base64.urlsafe_b64encode(json.dumps(payload_data).encode()).decode().rstrip("=")
    signature = hmac.new(get_jwt_secret().encode(), f"{header}.{payload}".encode(), hashlib.sha256).hexdigest()
    return f"{header}.{payload}.{signature}"

def decode_token(token: str) -> dict | None:
    """Decode and verify token. Returns payload dict or None."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header, payload, sig = parts
        expected_sig = hmac.new(get_jwt_secret().encode(), f"{header}.{payload}".encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return None
        # Pad base64
        padded = payload + "=" * (4 - len(payload) % 4)
        data = json.loads(base64.urlsafe_b64decode(padded))
        if data.get("exp", 0) < time.time():
            return None
        return data
    except Exception:
        return None

def get_user_id_from_token(token: str) -> int | None:
    """Extract user_id from token."""
    data = decode_token(token)
    if data:
        return int(data["sub"])
    return None
