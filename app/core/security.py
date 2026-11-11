import time
import hashlib
import hmac
import secrets
import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict
import jwt
from app.config import settings

logger = logging.getLogger(__name__)

# Session Cookie & Security Configuration
SESSION_COOKIE_NAME = "autoshorts_session"
JWT_ALGORITHM = "HS256"
SESSION_DURATION_SECONDS = 604800  # 7 days (604,800 seconds)
COOKIE_MAX_AGE = SESSION_DURATION_SECONDS
COOKIE_SAMESITE = "lax"
COOKIE_HTTPONLY = True

# Rate Limiter Configuration: 5 failed attempts within 15 minutes (900s)
LOGIN_MAX_FAILED_ATTEMPTS = 5
LOGIN_LOCKOUT_SECONDS = 900  # 15 minutes


def hash_password(password: str) -> str:
    """
    Hash password using PBKDF2-HMAC-SHA256 with 200,000 rounds and a unique 16-byte random salt.
    Format returned: salt$hex_derived_key
    """
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        200_000
    )
    return f"{salt}${key.hex()}"


def verify_password(password: str, hashed_password: str) -> bool:
    """
    Verify password against stored salt$hash in constant time using hmac.compare_digest.
    """
    try:
        if not hashed_password or "$" not in hashed_password:
            return False
        salt, expected_hash = hashed_password.split("$", 1)
        key = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            200_000
        )
        return hmac.compare_digest(key.hex(), expected_hash)
    except Exception as e:
        logger.warning(f"Password verification comparison error: {e}")
        return False


def create_session_token(
    user_id: str,
    username: str,
    role: str = "operator",
    expires_in_seconds: int = SESSION_DURATION_SECONDS
) -> str:
    """
    Generate signed JWT session token containing user identity and role claims.
    """
    expire = datetime.utcnow() + timedelta(seconds=expires_in_seconds)
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": str(role),
        "exp": expire,
        "iat": datetime.utcnow()
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_session_token(token: str) -> Optional[dict]:
    """
    Verify and decode signed JWT session token using application SECRET_KEY.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError) as e:
        logger.debug(f"Invalid or expired session token: {e}")
        return None


class LoginRateLimiter:
    """
    Dual-backend rate limiter for /login endpoint.
    Attempts to use Redis; gracefully falls back to an in-memory sliding window cache.
    Blocks client IP after 5 failed attempts within 15 minutes.
    """

    def __init__(
        self,
        max_attempts: int = LOGIN_MAX_FAILED_ATTEMPTS,
        window_seconds: int = LOGIN_LOCKOUT_SECONDS,
        redis_url: Optional[str] = None
    ):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.redis_client = None
        self._in_memory_cache: Dict[str, list] = {}

        # Attempt to initialize Redis connection
        url = redis_url or settings.REDIS_URL
        if url:
            try:
                import redis
                self.redis_client = redis.from_url(url, socket_timeout=1.5, socket_connect_timeout=1.5)
                # Ping Redis to test connectivity
                self.redis_client.ping()
                logger.info("LoginRateLimiter initialized with Redis backend.")
            except Exception as e:
                logger.warning(f"Redis unavailable for LoginRateLimiter ({e}). Falling back to in-memory store.")
                self.redis_client = None

    def is_rate_limited(self, ip_address: str) -> Tuple[bool, int]:
        """
        Check if IP address is currently blocked.
        Returns: (is_blocked: bool, retry_after_seconds: int)
        """
        ip = (ip_address or "127.0.0.1").strip()
        now = time.time()

        if self.redis_client:
            try:
                key = f"login_failures:{ip}"
                count = self.redis_client.get(key)
                if count and int(count) >= self.max_attempts:
                    ttl = self.redis_client.ttl(key)
                    return True, max(1, int(ttl))
                return False, 0
            except Exception as e:
                logger.warning(f"Redis rate check failed ({e}). Falling back to memory.")

        # In-Memory Fallback
        attempts = self._in_memory_cache.get(ip, [])
        # Prune attempts older than window_seconds
        valid_attempts = [ts for ts in attempts if now - ts < self.window_seconds]
        self._in_memory_cache[ip] = valid_attempts

        if len(valid_attempts) >= self.max_attempts:
            oldest = valid_attempts[0]
            remaining = int(self.window_seconds - (now - oldest))
            return True, max(1, remaining)

        return False, 0

    def record_failure(self, ip_address: str) -> int:
        """
        Record a failed login attempt for the given IP address.
        Returns current failure count.
        """
        ip = (ip_address or "127.0.0.1").strip()
        now = time.time()

        if self.redis_client:
            try:
                key = f"login_failures:{ip}"
                new_count = self.redis_client.incr(key)
                if new_count == 1:
                    self.redis_client.expire(key, self.window_seconds)
                return int(new_count)
            except Exception as e:
                logger.warning(f"Redis record failure failed ({e}). Using in-memory fallback.")

        # In-Memory Fallback
        attempts = self._in_memory_cache.get(ip, [])
        valid_attempts = [ts for ts in attempts if now - ts < self.window_seconds]
        valid_attempts.append(now)
        self._in_memory_cache[ip] = valid_attempts
        return len(valid_attempts)

    def reset(self, ip_address: str) -> None:
        """
        Reset failed login count upon successful authentication.
        """
        ip = (ip_address or "127.0.0.1").strip()
        if self.redis_client:
            try:
                self.redis_client.delete(f"login_failures:{ip}")
            except Exception as e:
                logger.warning(f"Redis reset failed ({e}).")

        self._in_memory_cache.pop(ip, None)


# Global singleton instance of the LoginRateLimiter
login_rate_limiter = LoginRateLimiter()
