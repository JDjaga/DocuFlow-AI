"""Password hashing and JWT token helpers.

WHAT THIS FILE DOES
    - hashes a plain password with bcrypt (one way, cannot be reversed)
    - verifies a plain password against a stored hash
    - creates a signed JWT access token
    - decodes/validates a JWT and returns its payload (or None)

WHY IT EXISTS
    Security primitives live in one small module, so routers never deal
    with hashing or token internals directly.

HOW IT CONNECTS
    auth_service.py uses hash/verify when registering and logging in.
    dependencies/authentication.py uses decode_access_token on every
    protected request to find out WHO is calling.

WHY NOT PASSLIB
    passlib 1.7.4 (the last release) crashes with bcrypt >= 4.1 because it
    still reads bcrypt.__about__.__version__, which was removed upstream.
    Calling the well maintained `bcrypt` library directly removes that
    broken dependency and is just as secure - a good real-world example of
    checking your dependency chain instead of copying old boilerplate.

INTERVIEW NOTE
    "Passwords are stored only as bcrypt hashes (with a per-password salt
     built into bcrypt). Tokens are signed, not encrypted, with HS256 and
     carry an exp claim, so the server can validate them without a DB hit."
"""
from datetime import datetime, timedelta, timezone

from bcrypt import checkpw, gensalt, hashpw
from jose import JWTError, jwt

from app.core.config import settings

BCRYPT_ROUNDS = 12
PASSWORD_MAX_BYTES = 72  # bcrypt silently ignores anything after 72 bytes


def hash_password(password: str) -> str:
    """Return a bcrypt hash of the plain password."""
    # bcrypt only considers the first 72 bytes; truncating explicitly keeps
    # hash and verify behaviour identical for very long passwords.
    truncated = password.encode("utf-8")[:PASSWORD_MAX_BYTES]
    return hashpw(truncated, gensalt(rounds=BCRYPT_ROUNDS)).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Check a plain password against the stored hash."""
    try:
        return checkpw(plain_password.encode("utf-8")[:PASSWORD_MAX_BYTES], hashed_password.encode("utf-8"))
    except (ValueError, TypeError):
        # Malformed hash stored in the DB -> treat it as a wrong password.
        return False


def create_access_token(subject: str, extra_claims: dict | None = None) -> str:
    """Create a signed JWT where `subject` is the user id as a string."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload: dict = {"sub": str(subject), "exp": expire, "iat": now}
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    """Decode a JWT. Returns None when it is expired, tampered or malformed."""
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None
