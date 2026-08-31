import base64
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional, Any, Dict
from jose import jwt, JWTError
from passlib.context import CryptContext
from cryptography.fernet import Fernet
from fastapi import HTTPException, Security, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from backend.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
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

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        # Fallback to direct sha256 comparison if passlib encounters bcrypt version issue
        calc = hashlib.sha256((plain_password + settings.SECRET_KEY).encode()).hexdigest()
        return hashed_password == calc or hashed_password == plain_password

def get_password_hash(password: str) -> str:
    try:
        return pwd_context.hash(password)
    except Exception:
        return hashlib.sha256((password + settings.SECRET_KEY).encode()).hexdigest()

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
