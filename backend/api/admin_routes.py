import os
import re
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Request, status, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from backend.db.database import get_db
from backend.db.models import (
    ProviderConfig, GlobalInstruction, SSOConfig, User, UserRole,
    AuditLog, ReviewSession, HumanFeedback, ArchitectureSource
)
from backend.api.auth_routes import require_admin, log_security_event, get_client_ip
from backend.core.security import (
    encrypt_secret, decrypt_secret, get_password_hash, validate_password_strength
)
from backend.core.source_extractor import extract_source_content

router = APIRouter(prefix="/api/admin", tags=["Administration"])

class SourceCreateRequest(BaseModel):
    name: str
    source_type: str # excel, pdf, word, url
    target_agent: Optional[str] = "global"
    url: Optional[str] = None
    filename: Optional[str] = None
    description: Optional[str] = None
    extracted_text: Optional[str] = None
    is_active: bool = True

class SourceUpdateRequest(BaseModel):
    name: Optional[str] = None
    source_type: Optional[str] = None
    target_agent: Optional[str] = None
    url: Optional[str] = None
    filename: Optional[str] = None
    description: Optional[str] = None
    extracted_text: Optional[str] = None
    is_active: Optional[bool] = None

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

class GuidelineUpdateRequest(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None
    is_active: Optional[bool] = None

class SSOUpdateRequest(BaseModel):
    provider_type: str = "okta"
    is_enabled: bool = False
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    domain: Optional[str] = None
    redirect_uri: Optional[str] = None
    metadata_url: Optional[str] = None

class AdminUserCreateRequest(BaseModel):
    email: str
    password: str
    full_name: Optional[str] = None
    role: Optional[UserRole] = UserRole.REVIEWER
    is_active: bool = True

class AdminUserUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None

class UserRoleUpdateRequest(BaseModel):
    role: UserRole

class UserStatusUpdateRequest(BaseModel):
    is_active: bool

class AdminResetPasswordRequest(BaseModel):
    new_password: str

@router.get("/providers")
def list_providers(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    """List all LLM provider configs (AWS, Google, Anthropic, OpenAI, Mistral)."""
    from backend.core.llm_router import LLMRouter
    active_providers = LLMRouter.get_active_providers()
    providers = ["google", "anthropic", "openai", "mistral", "aws", "mock"]
    existing = {p.provider_name: p for p in db.query(ProviderConfig).all()}

    results = []
    for p_name in providers:
        cfg = existing.get(p_name)
        has_db_key = bool(cfg and cfg.api_key_encrypted)
        
        # Check if key is available in env vars
        has_env_key = False
        import os
        from backend.config import settings
        if p_name == "google":
            has_env_key = bool(settings.GOOGLE_API_KEY or os.getenv("GOOGLE_API_KEY"))
        elif p_name == "anthropic":
            has_env_key = bool(settings.ANTHROPIC_API_KEY or os.getenv("ANTHROPIC_API_KEY"))
        elif p_name == "openai":
            has_env_key = bool(settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY"))
        elif p_name == "mistral":
            has_env_key = bool(settings.MISTRAL_API_KEY or os.getenv("MISTRAL_API_KEY"))
        elif p_name == "aws":
            has_env_key = bool(settings.AWS_ACCESS_KEY_ID or os.getenv("AWS_ACCESS_KEY_ID"))
        elif p_name == "mock":
            has_env_key = True # mock always works
            
        results.append({
            "provider_name": p_name,
            "is_enabled": cfg.is_enabled if cfg else True,
            "default_model": cfg.default_model if cfg else None,
            "has_api_key": has_db_key or has_env_key,
            "masked_key": "••••••••••••" + (decrypt_secret(cfg.api_key_encrypted)[-4:] if has_db_key else "") if has_db_key else None
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
    if provider_name not in ["google", "anthropic", "openai", "mistral", "aws", "mock"]:
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
        "created_at": g.created_at.isoformat() if g.created_at else None,
        "updated_at": g.updated_at.isoformat() if g.updated_at else None
    } for g in guidelines]

@router.post("/guidelines")
def create_guideline(
    req: GuidelineCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin)
):
    clean_title = req.title.strip() if req.title else ""
    clean_content = req.content.strip() if req.content else ""
    if not clean_title:
        raise HTTPException(status_code=400, detail="Guideline title cannot be empty.")
    if not clean_content:
        raise HTTPException(status_code=400, detail="Guideline content cannot be empty.")

    instruction = GlobalInstruction(
        title=clean_title,
        content=clean_content,
        category=(req.category or "general").strip().lower(),
        is_active=req.is_active
    )
    db.add(instruction)
    db.commit()
    db.refresh(instruction)

    client_ip = get_client_ip(request)
    log_security_event(
        db=db,
        action="GUIDELINE_CREATED",
        details=f"Admin '{admin_user.email}' created guideline '{instruction.title}' ({instruction.category})",
        user_id=admin_user.id,
        user_email=admin_user.email,
        ip_address=client_ip
    )

    return {
        "status": "created",
        "id": instruction.id,
        "title": instruction.title,
        "content": instruction.content,
        "category": instruction.category,
        "is_active": instruction.is_active,
        "created_at": instruction.created_at.isoformat() if instruction.created_at else None,
        "updated_at": instruction.updated_at.isoformat() if instruction.updated_at else None
    }

@router.put("/guidelines/{guideline_id}")
@router.patch("/guidelines/{guideline_id}")
def update_guideline(
    guideline_id: str,
    req: GuidelineUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin)
):
    instruction = db.query(GlobalInstruction).filter(GlobalInstruction.id == guideline_id).first()
    if not instruction:
        raise HTTPException(status_code=404, detail="Guideline not found")

    updated_fields = []
    if req.title is not None:
        clean_title = req.title.strip()
        if not clean_title:
            raise HTTPException(status_code=400, detail="Guideline title cannot be empty.")
        instruction.title = clean_title
        updated_fields.append("title")

    if req.content is not None:
        clean_content = req.content.strip()
        if not clean_content:
            raise HTTPException(status_code=400, detail="Guideline content cannot be empty.")
        instruction.content = clean_content
        updated_fields.append("content")

    if req.category is not None:
        clean_cat = req.category.strip().lower()
        if clean_cat:
            instruction.category = clean_cat
            updated_fields.append("category")

    if req.is_active is not None:
        instruction.is_active = req.is_active
        updated_fields.append(f"is_active={req.is_active}")

    instruction.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(instruction)

    client_ip = get_client_ip(request)
    log_security_event(
        db=db,
        action="GUIDELINE_UPDATED",
        details=f"Admin '{admin_user.email}' updated guideline '{instruction.title}' [{', '.join(updated_fields) if updated_fields else 'no changes'}]",
        user_id=admin_user.id,
        user_email=admin_user.email,
        ip_address=client_ip
    )

    return {
        "status": "updated",
        "id": instruction.id,
        "title": instruction.title,
        "content": instruction.content,
        "category": instruction.category,
        "is_active": instruction.is_active,
        "created_at": instruction.created_at.isoformat() if instruction.created_at else None,
        "updated_at": instruction.updated_at.isoformat() if instruction.updated_at else None
    }

@router.delete("/guidelines/{guideline_id}")
def delete_guideline(
    guideline_id: str,
    request: Request,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin)
):
    instruction = db.query(GlobalInstruction).filter(GlobalInstruction.id == guideline_id).first()
    if not instruction:
        raise HTTPException(status_code=404, detail="Guideline not found")
    
    title = instruction.title
    db.delete(instruction)
    db.commit()

    client_ip = get_client_ip(request)
    log_security_event(
        db=db,
        action="GUIDELINE_DELETED",
        details=f"Admin '{admin_user.email}' deleted guideline '{title}' (id={guideline_id})",
        user_id=admin_user.id,
        user_email=admin_user.email,
        ip_address=client_ip
    )

    return {"status": "deleted", "id": guideline_id}

# --------------------------------------------------------------------------
# Architecture Sources (Excel, PDF, Word, URL) Management
# --------------------------------------------------------------------------
SOURCES_STORAGE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "sources")
os.makedirs(SOURCES_STORAGE_DIR, exist_ok=True)

@router.get("/sources")
def list_sources(
    target_agent: Optional[str] = None,
    source_type: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin)
):
    query = db.query(ArchitectureSource)
    if target_agent:
        query = query.filter(ArchitectureSource.target_agent == target_agent.strip().lower())
    if source_type:
        query = query.filter(ArchitectureSource.source_type == source_type.strip().lower())
    if is_active is not None:
        query = query.filter(ArchitectureSource.is_active == is_active)
    
    sources = query.order_by(ArchitectureSource.created_at.desc()).all()
    return [{
        "id": s.id,
        "name": s.name,
        "source_type": s.source_type,
        "target_agent": s.target_agent,
        "url": s.url,
        "filename": s.filename,
        "file_size": s.file_size,
        "description": s.description,
        "extracted_text": s.extracted_text,
        "is_active": s.is_active,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None
    } for s in sources]

@router.post("/sources")
async def create_source(
    request: Request,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin)
):
    content_type = request.headers.get("content-type", "")
    name = ""
    source_type = "url"
    target_agent = "global"
    url = None
    description = None
    extracted_text = None
    is_active = True
    filename = None
    file_bytes = None
    file_size = None

    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        name = str(form.get("name", "")).strip()
        source_type = str(form.get("source_type", "url")).strip().lower()
        target_agent = str(form.get("target_agent", "global")).strip().lower()
        url = str(form.get("url", "")).strip() or None
        description = str(form.get("description", "")).strip() or None
        extracted_text = str(form.get("extracted_text", "")).strip() or None
        is_active = str(form.get("is_active", "true")).lower() in ("true", "1", "yes")

        file_field = form.get("file")
        if file_field and hasattr(file_field, "filename") and file_field.filename:
            filename = file_field.filename
            file_bytes = await file_field.read()
            file_size = len(file_bytes)
    else:
        try:
            body = await request.json()
        except Exception:
            body = {}
        name = str(body.get("name", "")).strip()
        source_type = str(body.get("source_type", "url")).strip().lower()
        target_agent = str(body.get("target_agent", "global")).strip().lower()
        url = body.get("url")
        description = body.get("description")
        extracted_text = body.get("extracted_text")
        is_active = bool(body.get("is_active", True))
        filename = body.get("filename")

    if not name:
        raise HTTPException(status_code=400, detail="Source name is required.")
    
    if source_type not in ("excel", "pdf", "word", "url"):
        raise HTTPException(status_code=400, detail="source_type must be excel, pdf, word, or url.")

    source_id = str(uuid.uuid4())
    stored_file_path = None

    if file_bytes and filename:
        safe_fname = re.sub(r"[^a-zA-Z0-9_.-]", "_", filename)
        disk_filename = f"{source_id}_{safe_fname}"
        stored_file_path = os.path.join(SOURCES_STORAGE_DIR, disk_filename)
        with open(stored_file_path, "wb") as f:
            f.write(file_bytes)

    if not extracted_text:
        extracted_text = extract_source_content(
            source_type=source_type,
            file_bytes=file_bytes,
            filename=filename,
            url=url
        )

    source = ArchitectureSource(
        id=source_id,
        name=name,
        source_type=source_type,
        target_agent=target_agent,
        url=url,
        filename=filename,
        file_path=stored_file_path,
        file_size=file_size,
        description=description,
        extracted_text=extracted_text,
        is_active=is_active
    )
    db.add(source)
    db.commit()
    db.refresh(source)

    client_ip = get_client_ip(request)
    log_security_event(
        db=db,
        action="SOURCE_CREATED",
        details=f"Admin '{admin_user.email}' added {source.source_type.upper()} source '{source.name}' targeted to '{source.target_agent}'",
        user_id=admin_user.id,
        user_email=admin_user.email,
        ip_address=client_ip
    )

    return {
        "status": "created",
        "id": source.id,
        "name": source.name,
        "source_type": source.source_type,
        "target_agent": source.target_agent,
        "url": source.url,
        "filename": source.filename,
        "file_size": source.file_size,
        "description": source.description,
        "extracted_text": source.extracted_text,
        "is_active": source.is_active,
        "created_at": source.created_at.isoformat() if source.created_at else None,
        "updated_at": source.updated_at.isoformat() if source.updated_at else None
    }

@router.put("/sources/{source_id}")
@router.patch("/sources/{source_id}")
async def update_source(
    source_id: str,
    request: Request,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin)
):
    source = db.query(ArchitectureSource).filter(ArchitectureSource.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    content_type = request.headers.get("content-type", "")
    name = None
    source_type = None
    target_agent = None
    url = None
    description = None
    extracted_text = None
    is_active = None
    file_bytes = None
    filename = None

    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        if "name" in form:
            name = str(form.get("name")).strip()
        if "source_type" in form:
            source_type = str(form.get("source_type")).strip().lower()
        if "target_agent" in form:
            target_agent = str(form.get("target_agent")).strip().lower()
        if "url" in form:
            url = str(form.get("url")).strip() or None
        if "description" in form:
            description = str(form.get("description")).strip() or None
        if "extracted_text" in form:
            extracted_text = str(form.get("extracted_text")).strip() or None
        if "is_active" in form:
            is_active = str(form.get("is_active")).lower() in ("true", "1", "yes")

        file_field = form.get("file")
        if file_field and hasattr(file_field, "filename") and file_field.filename:
            filename = file_field.filename
            file_bytes = await file_field.read()
    else:
        try:
            body = await request.json()
        except Exception:
            body = {}
        if "name" in body:
            name = str(body.get("name")).strip()
        if "source_type" in body:
            source_type = str(body.get("source_type")).strip().lower()
        if "target_agent" in body:
            target_agent = str(body.get("target_agent")).strip().lower()
        if "url" in body:
            url = body.get("url")
        if "description" in body:
            description = body.get("description")
        if "extracted_text" in body:
            extracted_text = body.get("extracted_text")
        if "is_active" in body:
            is_active = bool(body.get("is_active"))

    updated_fields = []
    if name is not None:
        if not name:
            raise HTTPException(status_code=400, detail="Source name cannot be empty.")
        source.name = name
        updated_fields.append("name")

    if source_type is not None:
        if source_type not in ("excel", "pdf", "word", "url"):
            raise HTTPException(status_code=400, detail="Invalid source_type.")
        source.source_type = source_type
        updated_fields.append("source_type")

    if target_agent is not None:
        source.target_agent = target_agent
        updated_fields.append("target_agent")

    if url is not None:
        source.url = url
        updated_fields.append("url")

    if description is not None:
        source.description = description
        updated_fields.append("description")

    if is_active is not None:
        source.is_active = is_active
        updated_fields.append(f"is_active={is_active}")

    if file_bytes and filename:
        if source.file_path and os.path.exists(source.file_path):
            try:
                os.remove(source.file_path)
            except Exception:
                pass

        safe_fname = re.sub(r"[^a-zA-Z0-9_.-]", "_", filename)
        disk_filename = f"{source.id}_{safe_fname}"
        stored_file_path = os.path.join(SOURCES_STORAGE_DIR, disk_filename)
        with open(stored_file_path, "wb") as f:
            f.write(file_bytes)

        source.filename = filename
        source.file_path = stored_file_path
        source.file_size = len(file_bytes)
        source.extracted_text = extract_source_content(
            source_type=source.source_type,
            file_bytes=file_bytes,
            filename=filename,
            url=source.url
        )
        updated_fields.append("file")
    elif extracted_text is not None:
        source.extracted_text = extracted_text
        updated_fields.append("extracted_text")

    source.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(source)

    client_ip = get_client_ip(request)
    log_security_event(
        db=db,
        action="SOURCE_UPDATED",
        details=f"Admin '{admin_user.email}' updated source '{source.name}' [{', '.join(updated_fields) if updated_fields else 'no changes'}]",
        user_id=admin_user.id,
        user_email=admin_user.email,
        ip_address=client_ip
    )

    return {
        "status": "updated",
        "id": source.id,
        "name": source.name,
        "source_type": source.source_type,
        "target_agent": source.target_agent,
        "url": source.url,
        "filename": source.filename,
        "file_size": source.file_size,
        "description": source.description,
        "extracted_text": source.extracted_text,
        "is_active": source.is_active,
        "created_at": source.created_at.isoformat() if source.created_at else None,
        "updated_at": source.updated_at.isoformat() if source.updated_at else None
    }

@router.delete("/sources/{source_id}")
def delete_source(
    source_id: str,
    request: Request,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin)
):
    source = db.query(ArchitectureSource).filter(ArchitectureSource.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    name = source.name
    if source.file_path and os.path.exists(source.file_path):
        try:
            os.remove(source.file_path)
        except Exception:
            pass

    db.delete(source)
    db.commit()

    client_ip = get_client_ip(request)
    log_security_event(
        db=db,
        action="SOURCE_DELETED",
        details=f"Admin '{admin_user.email}' deleted source '{name}' (id={source_id})",
        user_id=admin_user.id,
        user_email=admin_user.email,
        ip_address=client_ip
    )

    return {"status": "deleted", "id": source_id}

@router.get("/sources/{source_id}/download")
def download_source_file(
    source_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin)
):
    source = db.query(ArchitectureSource).filter(ArchitectureSource.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    if not source.file_path or not os.path.exists(source.file_path):
        raise HTTPException(status_code=404, detail="Source file not stored locally.")
    return FileResponse(source.file_path, filename=source.filename or "source_document")

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
def list_users(
    search: Optional[str] = None,
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin)
):
    """Lists users with optional search and filtering."""
    query = db.query(User)
    if search:
        s = f"%{search.strip()}%"
        query = query.filter((User.email.ilike(s)) | (User.full_name.ilike(s)))
    if role:
        query = query.filter(User.role == role)
    if is_active is not None:
        query = query.filter(User.is_active == is_active)
    
    users = query.order_by(User.created_at.desc()).all()
    results = []
    for u in users:
        reviews_count = db.query(ReviewSession).filter(ReviewSession.created_by_id == u.id).count()
        results.append({
            "id": u.id,
            "email": u.email,
            "full_name": u.full_name,
            "role": u.role.value,
            "is_active": u.is_active,
            "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "reviews_count": reviews_count
        })
    return results

@router.post("/users")
def create_user(
    req: AdminUserCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin)
):
    """Admin creates a new user directly with specified role and password."""
    clean_email = req.email.strip().lower()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", clean_email):
        raise HTTPException(status_code=400, detail="Invalid email format")
    
    pwd_err = validate_password_strength(req.password)
    if pwd_err:
        raise HTTPException(status_code=400, detail=pwd_err)
    
    existing = db.query(User).filter(User.email.ilike(clean_email)).first()
    if existing:
        raise HTTPException(status_code=400, detail="An account with this email already exists")
    
    clean_name = req.full_name.strip() if req.full_name else clean_email.split("@")[0].capitalize()
    new_user = User(
        email=clean_email,
        hashed_password=get_password_hash(req.password),
        full_name=clean_name,
        role=req.role or UserRole.REVIEWER,
        is_active=req.is_active,
        created_at=datetime.now(timezone.utc)
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    client_ip = get_client_ip(request)
    log_security_event(
        db=db,
        action="USER_CREATED",
        details=f"Admin '{admin_user.email}' created user '{new_user.email}' with role {new_user.role.value}",
        user_id=admin_user.id,
        user_email=admin_user.email,
        ip_address=client_ip
    )

    return {
        "status": "success",
        "user": {
            "id": new_user.id,
            "email": new_user.email,
            "full_name": new_user.full_name,
            "role": new_user.role.value,
            "is_active": new_user.is_active,
            "created_at": new_user.created_at.isoformat() if new_user.created_at else None
        }
    }

@router.get("/users/{user_id}")
def get_user_details(
    user_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin)
):
    """Retrieves full details for a specific user."""
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    
    reviews_count = db.query(ReviewSession).filter(ReviewSession.created_by_id == u.id).count()
    feedbacks_count = db.query(HumanFeedback).filter(HumanFeedback.user_id == u.id).count()
    return {
        "id": u.id,
        "email": u.email,
        "full_name": u.full_name,
        "role": u.role.value,
        "is_active": u.is_active,
        "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
        "created_at": u.created_at.isoformat() if u.created_at else None,
        "updated_at": u.updated_at.isoformat() if u.updated_at else None,
        "reviews_count": reviews_count,
        "feedbacks_count": feedbacks_count
    }

@router.put("/users/{user_id}")
def update_user(
    user_id: str,
    req: AdminUserUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin)
):
    """Updates user information with administrative protection checks."""
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    
    changes = []
    # Check if demoting the last active admin
    if req.role and req.role != target.role:
        if target.role == UserRole.ADMIN and req.role != UserRole.ADMIN:
            admin_count = db.query(User).filter(User.role == UserRole.ADMIN, User.is_active == True).count()
            if admin_count <= 1:
                raise HTTPException(status_code=400, detail="Cannot demote the last active Administrator")
        changes.append(f"role: {target.role.value} -> {req.role.value}")
        target.role = req.role

    # Check if deactivating self or last active admin
    if req.is_active is not None and req.is_active != target.is_active:
        if not req.is_active:
            if target.id == admin_user.id:
                raise HTTPException(status_code=400, detail="You cannot deactivate your own administrative account")
            if target.role == UserRole.ADMIN:
                admin_count = db.query(User).filter(User.role == UserRole.ADMIN, User.is_active == True).count()
                if admin_count <= 1:
                    raise HTTPException(status_code=400, detail="Cannot deactivate the last active Administrator")
        changes.append(f"is_active: {target.is_active} -> {req.is_active}")
        target.is_active = req.is_active

    if req.email and req.email.strip().lower() != target.email.lower():
        clean_email = req.email.strip().lower()
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", clean_email):
            raise HTTPException(status_code=400, detail="Invalid email format")
        existing = db.query(User).filter(User.email.ilike(clean_email), User.id != user_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="An account with this email already exists")
        changes.append(f"email: {target.email} -> {clean_email}")
        target.email = clean_email

    if req.full_name is not None and req.full_name.strip() != (target.full_name or ""):
        changes.append(f"full_name: {target.full_name} -> {req.full_name.strip()}")
        target.full_name = req.full_name.strip()

    target.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(target)

    client_ip = get_client_ip(request)
    log_security_event(
        db=db,
        action="USER_UPDATED",
        details=f"Admin '{admin_user.email}' updated user '{target.email}': {', '.join(changes) if changes else 'no changes'}",
        user_id=admin_user.id,
        user_email=admin_user.email,
        ip_address=client_ip
    )

    return {
        "status": "success",
        "user": {
            "id": target.id,
            "email": target.email,
            "full_name": target.full_name,
            "role": target.role.value,
            "is_active": target.is_active,
            "created_at": target.created_at.isoformat() if target.created_at else None
        }
    }

@router.put("/users/{user_id}/role")
def update_user_role(
    user_id: str,
    req: UserRoleUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin)
):
    """Updates user role with protection for the last admin."""
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    
    if target.role == UserRole.ADMIN and req.role != UserRole.ADMIN:
        admin_count = db.query(User).filter(User.role == UserRole.ADMIN, User.is_active == True).count()
        if admin_count <= 1:
            raise HTTPException(status_code=400, detail="Cannot demote the last active Administrator")
    
    old_role = target.role.value
    target.role = req.role
    target.updated_at = datetime.now(timezone.utc)
    db.commit()

    client_ip = get_client_ip(request)
    log_security_event(
        db=db,
        action="USER_ROLE_CHANGED",
        details=f"Admin '{admin_user.email}' changed user '{target.email}' role from {old_role} to {req.role.value}",
        user_id=admin_user.id,
        user_email=admin_user.email,
        ip_address=client_ip
    )

    return {"status": "success", "user_id": target.id, "role": target.role.value}

@router.put("/users/{user_id}/status")
def toggle_user_status(
    user_id: str,
    req: UserStatusUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin)
):
    """Toggles active/inactive status for a user."""
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    
    if not req.is_active:
        if target.id == admin_user.id:
            raise HTTPException(status_code=400, detail="You cannot deactivate your own account")
        if target.role == UserRole.ADMIN:
            admin_count = db.query(User).filter(User.role == UserRole.ADMIN, User.is_active == True).count()
            if admin_count <= 1:
                raise HTTPException(status_code=400, detail="Cannot deactivate the last active Administrator")

    target.is_active = req.is_active
    target.updated_at = datetime.now(timezone.utc)
    db.commit()

    client_ip = get_client_ip(request)
    action_str = "activated" if req.is_active else "deactivated"
    log_security_event(
        db=db,
        action="USER_STATUS_TOGGLED",
        details=f"Admin '{admin_user.email}' {action_str} user '{target.email}'",
        user_id=admin_user.id,
        user_email=admin_user.email,
        ip_address=client_ip
    )

    return {"status": "success", "user_id": target.id, "is_active": target.is_active}

@router.post("/users/{user_id}/reset-password")
def reset_user_password(
    user_id: str,
    req: AdminResetPasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin)
):
    """Allows an administrator to reset a user's password."""
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    
    pwd_err = validate_password_strength(req.new_password)
    if pwd_err:
        raise HTTPException(status_code=400, detail=pwd_err)
    
    target.hashed_password = get_password_hash(req.new_password)
    target.updated_at = datetime.now(timezone.utc)
    db.commit()

    client_ip = get_client_ip(request)
    log_security_event(
        db=db,
        action="PASSWORD_RESET_ADMIN",
        details=f"Admin '{admin_user.email}' reset password for user '{target.email}'",
        user_id=admin_user.id,
        user_email=admin_user.email,
        ip_address=client_ip
    )

    return {"status": "success", "message": f"Password for {target.email} has been reset successfully"}

@router.delete("/users/{user_id}")
def delete_user(
    user_id: str,
    request: Request,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin)
):
    """Deletes a user account with comprehensive integrity and safety checks."""
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    
    if target.id == admin_user.id:
        raise HTTPException(status_code=400, detail="You cannot delete your own account")
    
    if target.role == UserRole.ADMIN:
        admin_count = db.query(User).filter(User.role == UserRole.ADMIN).count()
        if admin_count <= 1:
            raise HTTPException(status_code=400, detail="Cannot delete the last Administrator account")
    
    target_email = target.email

    # Disassociate foreign keys safely before deletion so records are preserved
    db.query(AuditLog).filter(AuditLog.user_id == user_id).update({"user_id": None})
    db.query(ReviewSession).filter(ReviewSession.created_by_id == user_id).update({"created_by_id": None})
    db.query(HumanFeedback).filter(HumanFeedback.user_id == user_id).update({"user_id": None})
    
    db.delete(target)
    db.commit()

    client_ip = get_client_ip(request)
    log_security_event(
        db=db,
        action="USER_DELETED",
        details=f"Admin '{admin_user.email}' deleted user '{target_email}'",
        user_id=admin_user.id,
        user_email=admin_user.email,
        ip_address=client_ip
    )

    return {"status": "success", "message": f"User {target_email} deleted successfully"}

@router.get("/audit-logs")
def list_audit_logs(
    limit: int = 50,
    action: Optional[str] = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin)
):
    """Retrieves chronological security and administrative audit logs."""
    query = db.query(AuditLog)
    if action:
        query = query.filter(AuditLog.action.ilike(f"%{action.strip()}%"))
    logs = query.order_by(AuditLog.timestamp.desc()).limit(min(limit, 200)).all()
    return [{
        "id": l.id,
        "user_id": l.user_id,
        "user_email": l.user_email or (l.user.email if l.user else "System"),
        "action": l.action,
        "details": l.details,
        "ip_address": l.ip_address,
        "timestamp": l.timestamp.isoformat() if l.timestamp else None
    } for l in logs]

@router.get("/stats")
def get_admin_stats(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    """Summary metrics for the administrator dashboard."""
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active == True).count()
    admin_users = db.query(User).filter(User.role == UserRole.ADMIN).count()
    reviewer_users = db.query(User).filter(User.role == UserRole.REVIEWER).count()
    total_reviews = db.query(ReviewSession).count()
    total_audits = db.query(AuditLog).count()

    return {
        "total_users": total_users,
        "active_users": active_users,
        "admin_users": admin_users,
        "reviewer_users": reviewer_users,
        "total_reviews": total_reviews,
        "total_audits": total_audits
    }
