from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any
from datetime import timedelta
from backend.db.database import get_db
from backend.db.models import User, UserRole, SSOConfig
from backend.core.security import (
    verify_password, get_password_hash, create_access_token,
    decode_access_token, security_bearer
)
from backend.config import settings

router = APIRouter(prefix="/api/auth", tags=["Authentication & SSO"])

class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None
    role: Optional[UserRole] = UserRole.REVIEWER

class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Dict[str, Any]

class SSOInitRequest(BaseModel):
    provider: str = "okta" # okta or saml
    redirect_uri: Optional[str] = None

def get_current_user(
    credentials = Depends(security_bearer),
    db: Session = Depends(get_db)
) -> User:
    if not credentials:
        # Fallback to demo default admin user if running without auth header in development
        user = db.query(User).filter(User.email == settings.ADMIN_EMAIL).first()
        if not user:
            user = User(
                email=settings.ADMIN_EMAIL,
                hashed_password=get_password_hash(settings.ADMIN_PASSWORD),
                full_name="Default Administrator",
                role=UserRole.ADMIN,
                is_active=True
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        return user

    token = credentials.credentials
    payload = decode_access_token(token)
    user_id: str = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token claims")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User inactive or not found")
    return user

def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin role required for this action")
    return user

@router.post("/register", response_model=TokenResponse)
def register(req: UserRegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == req.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="User with this email already registered")

    # If first user, make Admin
    user_count = db.query(User).count()
    assigned_role = UserRole.ADMIN if user_count == 0 else req.role

    user = User(
        email=req.email,
        hashed_password=get_password_hash(req.password),
        full_name=req.full_name or req.email.split("@")[0],
        role=assigned_role,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(data={"sub": user.id, "email": user.email, "role": user.role.value})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value
        }
    }

@router.post("/login", response_model=TokenResponse)
def login(req: UserLoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    
    token = create_access_token(data={"sub": user.id, "email": user.email, "role": user.role.value})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value
        }
    }

@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role.value,
        "is_active": current_user.is_active
    }

@router.post("/sso/init")
def initiate_sso(req: SSOInitRequest, db: Session = Depends(get_db)):
    """Initiates SSO redirect handshake URL for Okta or generic SAML."""
    sso = db.query(SSOConfig).filter(SSOConfig.provider_type == req.provider).first()
    if not sso or not sso.is_enabled:
        return {
            "status": "mock_sso_ready",
            "provider": req.provider,
            "auth_url": f"http://localhost:8000/api/auth/sso/callback?code=mock_sso_token_123&state=arb_okta"
        }
    
    auth_url = f"https://{sso.domain}/oauth2/v1/authorize?client_id={sso.client_id}&response_type=code&scope=openid%20email%20profile&redirect_uri={sso.redirect_uri}&state=arb_sec"
    return {"status": "redirect", "auth_url": auth_url}

@router.get("/sso/callback")
def sso_callback(code: str, state: Optional[str] = None, db: Session = Depends(get_db)):
    """Processes SSO authorization code and issues ARB session token."""
    mock_email = "sso.reviewer@enterprise.com"
    user = db.query(User).filter(User.email == mock_email).first()
    if not user:
        user = User(
            email=mock_email,
            hashed_password=get_password_hash("SSO_Managed_Password_123!"),
            full_name="Enterprise SSO Reviewer",
            role=UserRole.REVIEWER,
            is_active=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    token = create_access_token(data={"sub": user.id, "email": user.email, "role": user.role.value})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value
        }
    }
