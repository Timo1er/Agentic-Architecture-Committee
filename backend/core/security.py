import base64
import hashlib
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Any, Dict
import bcrypt
from jose import jwt, JWTError
from cryptography.fernet import Fernet
from fastapi import HTTPException, Security, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from backend.config import settings

security_bearer = HTTPBearer(auto_error=False)

def _get_fernet() -> Fernet:
    """Generate or retrieve a 32-byte url-safe base64 Fernet key."""
    raw_key = settings.ENCRYPTION_KEY.encode()
    # Ensure key is exactly 32 bytes url-safe base64 encoded
    digest = hashlib.sha256(raw_key).digest()
    b64_key = base64.urlsafe_b64encode(digest)
    return Fernet(b64_key)

def encrypt_secret(plain_text: Optional[str]) -> Optional[str]:
    if not plain_text:
        return None
    f = _get_fernet()
    return f.encrypt(plain_text.encode()).decode()

def decrypt_secret(cipher_text: Optional[str]) -> Optional[str]:
    if not cipher_text:
        return None
    try:
        f = _get_fernet()
        return f.decrypt(cipher_text.encode()).decode()
    except Exception:
        return cipher_text # fallback if plaintext in dev

def validate_password_strength(password: str) -> Optional[str]:
    """Validate password strength according to enterprise security standards.
    Returns an error message string if invalid, or None if valid.
    """
    if not password or len(password) < 8:
        return "Password must be at least 8 characters long."
    if len(password) > 72:
        return "Password must not exceed 72 characters."
    if not re.search(r"[A-Za-z]", password):
        return "Password must contain at least one letter."
    if not re.search(r"\d", password):
        return "Password must contain at least one numeric digit."
    return None

def is_bcrypt_hash(hash_str: str) -> bool:
    """Check if the string is a valid bcrypt hash format."""
    return bool(hash_str and hash_str.startswith(("$2b$", "$2a$", "$2y$")))

def get_password_hash(password: str) -> str:
    """Generate secure bcrypt salt & hash with 12 work rounds."""
    pwd_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plain password against hashed password (bcrypt or legacy sha256)."""
    if not plain_password or not hashed_password:
        return False
    
    pwd_bytes = plain_password.encode("utf-8")[:72]
    
    # 1. Standard bcrypt verification
    if is_bcrypt_hash(hashed_password):
        try:
            return bcrypt.checkpw(pwd_bytes, hashed_password.encode("utf-8"))
        except Exception:
            return False

    # 2. Legacy SHA-256 fallback (for existing database hashes)
    calc = hashlib.sha256((plain_password + settings.SECRET_KEY).encode("utf-8")).hexdigest()
    return hashed_password == calc

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Creates a signed JWT access token with iat, exp, and jti claims."""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        
    to_encode.update({
        "exp": expire,
        "iat": now,
        "jti": str(uuid.uuid4()),
        "token_type": "access"
    })
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Dict[str, Any]:
    """Decodes and validates a signed JWT token."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials or token expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
