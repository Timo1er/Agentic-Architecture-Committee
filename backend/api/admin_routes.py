from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from backend.db.database import get_db
from backend.db.models import ProviderConfig, GlobalInstruction, SSOConfig, User, UserRole
from backend.api.auth_routes import require_admin
from backend.core.security import encrypt_secret, decrypt_secret

router = APIRouter(prefix="/api/admin", tags=["Administration"])

class ProviderUpdateRequest(BaseModel):
    is_enabled: bool
    api_key: Optional[str] = None
    default_model: Optional[str] = None
    extra_config: Optional[Dict[str, Any]] = None

class GuidelineCreateRequest(BaseModel):
    title: str
    content: str
    category: Optional[str] = "general"
    is_active: bool = True

class SSOUpdateRequest(BaseModel):
    provider_type: str = "okta"
    is_enabled: bool = False
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    domain: Optional[str] = None
    redirect_uri: Optional[str] = None
    metadata_url: Optional[str] = None

class UserRoleUpdateRequest(BaseModel):
    role: UserRole

@router.get("/providers")
def list_providers(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    """List all LLM provider configs (AWS, Google, Anthropic, OpenAI, Mistral)."""
    providers = ["google", "anthropic", "openai", "mistral", "aws"]
    existing = {p.provider_name: p for p in db.query(ProviderConfig).all()}

    results = []
    for p_name in providers:
        cfg = existing.get(p_name)
        has_key = bool(cfg and cfg.api_key_encrypted)
        results.append({
            "provider_name": p_name,
            "is_enabled": cfg.is_enabled if cfg else True,
            "default_model": cfg.default_model if cfg else None,
            "has_api_key": has_key,
            "masked_key": "••••••••••••" + (decrypt_secret(cfg.api_key_encrypted)[-4:] if has_key else "") if has_key else None
        })
    return results

@router.put("/providers/{provider_name}")
def update_provider(
    provider_name: str,
    req: ProviderUpdateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin)
):
    provider_name = provider_name.lower()
    if provider_name not in ["google", "anthropic", "openai", "mistral", "aws"]:
        raise HTTPException(status_code=400, detail="Unsupported provider name")

    config = db.query(ProviderConfig).filter(ProviderConfig.provider_name == provider_name).first()
    if not config:
        config = ProviderConfig(provider_name=provider_name)
        db.add(config)

    config.is_enabled = req.is_enabled
    if req.default_model:
        config.default_model = req.default_model
    if req.api_key:
        config.api_key_encrypted = encrypt_secret(req.api_key)

    db.commit()
    db.refresh(config)
    return {"status": "success", "provider_name": provider_name, "is_enabled": config.is_enabled}

@router.get("/guidelines")
def list_guidelines(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    guidelines = db.query(GlobalInstruction).order_by(GlobalInstruction.created_at.desc()).all()
    return [{
        "id": g.id,
        "title": g.title,
        "content": g.content,
        "category": g.category,
        "is_active": g.is_active,
        "created_at": g.created_at.isoformat()
    } for g in guidelines]

@router.post("/guidelines")
def create_guideline(req: GuidelineCreateRequest, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    instruction = GlobalInstruction(
        title=req.title,
        content=req.content,
        category=req.category or "general",
        is_active=req.is_active
    )
    db.add(instruction)
    db.commit()
    db.refresh(instruction)
    return {"status": "created", "id": instruction.id, "title": instruction.title}

@router.delete("/guidelines/{guideline_id}")
def delete_guideline(guideline_id: str, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    instruction = db.query(GlobalInstruction).filter(GlobalInstruction.id == guideline_id).first()
    if not instruction:
        raise HTTPException(status_code=404, detail="Guideline not found")
    db.delete(instruction)
    db.commit()
    return {"status": "deleted", "id": guideline_id}

@router.get("/sso")
def get_sso_settings(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    sso = db.query(SSOConfig).first()
    if not sso:
        return {
            "provider_type": "local",
            "is_enabled": False,
            "domain": None,
            "client_id": None,
            "redirect_uri": "http://localhost:8000/api/auth/sso/callback"
        }
    return {
        "id": sso.id,
        "provider_type": sso.provider_type,
        "is_enabled": sso.is_enabled,
        "domain": sso.domain,
        "client_id": sso.client_id,
        "redirect_uri": sso.redirect_uri,
        "metadata_url": sso.metadata_url
    }

@router.put("/sso")
def update_sso_settings(req: SSOUpdateRequest, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    sso = db.query(SSOConfig).first()
    if not sso:
        sso = SSOConfig()
        db.add(sso)

    sso.provider_type = req.provider_type
    sso.is_enabled = req.is_enabled
    sso.client_id = req.client_id
    if req.client_secret:
        sso.client_secret_encrypted = encrypt_secret(req.client_secret)
    sso.domain = req.domain
    sso.redirect_uri = req.redirect_uri
    sso.metadata_url = req.metadata_url

    db.commit()
    db.refresh(sso)
    return {"status": "success", "provider_type": sso.provider_type, "is_enabled": sso.is_enabled}

@router.get("/users")
def list_users(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    users = db.query(User).all()
    return [{
        "id": u.id,
        "email": u.email,
        "full_name": u.full_name,
        "role": u.role.value,
        "is_active": u.is_active,
        "created_at": u.created_at.isoformat()
    } for u in users]

@router.put("/users/{user_id}/role")
def update_user_role(
    user_id: str,
    req: UserRoleUpdateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.role = req.role
    db.commit()
    return {"status": "success", "user_id": user.id, "role": user.role.value}
