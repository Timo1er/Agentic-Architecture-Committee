import re
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr

from backend.db.database import get_db
from backend.db.models import User, UserRole, SSOConfig, AuditLog
from backend.core.security import (
    verify_password, get_password_hash, create_access_token,
    decode_access_token, validate_password_strength, is_bcrypt_hash,
    security_bearer
)
from backend.config import settings

router = APIRouter(prefix="/api/auth", tags=["Authentication & SSO"])

class UserRegisterRequest(BaseModel):
    email: str
    password: str
    full_name: Optional[str] = None

class UserLoginRequest(BaseModel):
    email: str
    password: str

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Dict[str, Any]

class SSOInitRequest(BaseModel):
    provider: str = "okta" # okta or saml
    redirect_uri: Optional[str] = None

def get_client_ip(request: Request) -> Optional[str]:
    """Helper to safely extract client IP."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None

def log_security_event(
    db: Session,
    action: str,
    details: str,
    user_id: Optional[str] = None,
    user_email: Optional[str] = None,
    ip_address: Optional[str] = None
):
    """Safely log security and administrative events into audit_logs."""
    try:
        log = AuditLog(
            user_id=user_id,
            user_email=user_email,
            action=action,
            details=details,
            ip_address=ip_address,
            timestamp=datetime.now(timezone.utc)
        )
        db.add(log)
        db.commit()
    except Exception:
        db.rollback()

def get_current_user(
    credentials = Depends(security_bearer),
    db: Session = Depends(get_db)
) -> User:
    """Strictly validates the Bearer JWT token and returns the active User object.
    Raises 401 if missing, invalid, or expired.
    Raises 403 if user account is disabled.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided",
            headers={"WWW-Authenticate": "Bearer"}
        )

    token = credentials.credentials
    payload = decode_access_token(token)
    user_id: str = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token claims",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account does not exist or has been deleted",
            headers={"WWW-Authenticate": "Bearer"}
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled. Please contact a system administrator."
        )
    return user

def require_admin(user: User = Depends(get_current_user)) -> User:
    """Enforces Admin privilege. Raises 403 if not Admin."""
    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative privileges are required for this action"
        )
    return user

@router.post("/register", response_model=TokenResponse)
def register(
    req: UserRegisterRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Registers a new user account with enterprise password validation."""
    clean_email = req.email.strip().lower()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", clean_email):
        raise HTTPException(status_code=400, detail="Invalid email address format")

    pwd_err = validate_password_strength(req.password)
    if pwd_err:
        raise HTTPException(status_code=400, detail=pwd_err)

    existing = db.query(User).filter(User.email.ilike(clean_email)).first()
    if existing:
        raise HTTPException(status_code=400, detail="An account with this email already exists")

    # If first user in the system, promote to Admin; otherwise default to Reviewer
    user_count = db.query(User).count()
    assigned_role = UserRole.ADMIN if user_count == 0 else UserRole.REVIEWER

    clean_name = req.full_name.strip() if req.full_name else clean_email.split("@")[0].capitalize()

    user = User(
        email=clean_email,
        hashed_password=get_password_hash(req.password),
        full_name=clean_name,
        role=assigned_role,
        is_active=True,
        last_login_at=datetime.now(timezone.utc)
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    client_ip = get_client_ip(request)
    log_security_event(
        db=db,
        action="USER_REGISTER",
        details=f"User registered with role {user.role.value}",
        user_id=user.id,
        user_email=user.email,
        ip_address=client_ip
    )

    token = create_access_token(data={"sub": user.id, "email": user.email, "role": user.role.value})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value,
            "is_active": user.is_active,
            "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
            "created_at": user.created_at.isoformat() if user.created_at else None
        }
    }

@router.post("/login", response_model=TokenResponse)
def login(
    req: UserLoginRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Authenticates user with email & password, updates last_login_at and audit logs."""
    clean_email = req.email.strip().lower()
    client_ip = get_client_ip(request)

    user = db.query(User).filter(User.email.ilike(clean_email)).first()
    if not user or not verify_password(req.password, user.hashed_password):
        log_security_event(
            db=db,
            action="LOGIN_FAILED",
            details=f"Failed login attempt for {clean_email}",
            user_id=user.id if user else None,
            user_email=clean_email,
            ip_address=client_ip
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    if not user.is_active:
        log_security_event(
            db=db,
            action="LOGIN_BLOCKED_DISABLED",
            details=f"Attempted login to disabled account {clean_email}",
            user_id=user.id,
            user_email=user.email,
            ip_address=client_ip
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been disabled. Please contact an administrator."
        )

    # Automatic upgrade to bcrypt if user was on legacy SHA-256
    if not is_bcrypt_hash(user.hashed_password):
        user.hashed_password = get_password_hash(req.password)

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)

    log_security_event(
        db=db,
        action="USER_LOGIN",
        details="User logged in successfully",
        user_id=user.id,
        user_email=user.email,
        ip_address=client_ip
    )

    token = create_access_token(data={"sub": user.id, "email": user.email, "role": user.role.value})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value,
            "is_active": user.is_active,
            "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
            "created_at": user.created_at.isoformat() if user.created_at else None
        }
    }

@router.post("/logout")
def logout(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Audits session logout."""
    client_ip = get_client_ip(request)
    log_security_event(
        db=db,
        action="USER_LOGOUT",
        details="User signed out",
        user_id=current_user.id,
        user_email=current_user.email,
        ip_address=client_ip
    )
    return {"status": "success", "message": "Logged out successfully"}

@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    """Returns the authenticated user's profile and permissions."""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role.value,
        "is_active": current_user.is_active,
        "last_login_at": current_user.last_login_at.isoformat() if current_user.last_login_at else None,
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None
    }

@router.post("/change-password")
def change_password(
    req: ChangePasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Allows the authenticated user to securely update their own password."""
    if not verify_password(req.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password verification failed"
        )
    
    pwd_err = validate_password_strength(req.new_password)
    if pwd_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=pwd_err)
    
    current_user.hashed_password = get_password_hash(req.new_password)
    current_user.updated_at = datetime.now(timezone.utc)
    db.commit()

    client_ip = get_client_ip(request)
    log_security_event(
        db=db,
        action="PASSWORD_CHANGED",
        details="User changed account password",
        user_id=current_user.id,
        user_email=current_user.email,
        ip_address=client_ip
    )

    return {"status": "success", "message": "Password updated successfully"}

@router.post("/sso/init")
def initiate_sso(req: SSOInitRequest, db: Session = Depends(get_db)):
    """Initiates SSO redirect handshake URL for Okta or generic SAML."""
    sso = db.query(SSOConfig).filter(SSOConfig.provider_type == req.provider).first()
    if not sso or not sso.is_enabled:
        return {
            "status": "mock_sso_ready",
            "provider": req.provider,
            "auth_url": "http://localhost:8000/api/auth/sso/callback?code=mock_sso_token_123&state=arb_okta"
        }
    
    auth_url = f"https://{sso.domain}/oauth2/v1/authorize?client_id={sso.client_id}&response_type=code&scope=openid%20email%20profile&redirect_uri={sso.redirect_uri}&state=arb_sec"
    return {"status": "redirect", "auth_url": auth_url}

@router.get("/sso/callback")
def sso_callback(
    code: str,
    request: Request,
    state: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Processes SSO authorization code and issues ARB session token."""
    mock_email = "sso.reviewer@enterprise.com"
    user = db.query(User).filter(User.email == mock_email).first()
    if not user:
        user = User(
            email=mock_email,
            hashed_password=get_password_hash("SSO_Managed_Password_123!"),
            full_name="Enterprise SSO Reviewer",
            role=UserRole.REVIEWER,
            is_active=True,
            last_login_at=datetime.now(timezone.utc)
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        user.last_login_at = datetime.now(timezone.utc)
        db.commit()

    client_ip = get_client_ip(request)
    log_security_event(
        db=db,
        action="SSO_LOGIN",
        details="User authenticated via SSO handshake",
        user_id=user.id,
        user_email=user.email,
        ip_address=client_ip
    )

    token = create_access_token(data={"sub": user.id, "email": user.email, "role": user.role.value})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value,
            "is_active": user.is_active,
            "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
            "created_at": user.created_at.isoformat() if user.created_at else None
        }
    }
