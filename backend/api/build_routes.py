import json
import logging
import uuid
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request, Response
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from backend.db.database import get_db
from backend.db.models import BuildArchitectureSession, User
from backend.api.auth_routes import get_current_user
from backend.core.source_extractor import extract_input_document, extract_source_content
from backend.core.llm_router import LLMRouter
from backend.agents.builder_agents import CloudArchitectureBuilder

logger = logging.getLogger("arb.build_routes")

router = APIRouter(prefix="/api/build", tags=["Build Architecture"])

class ProposeArchitectureRequest(BaseModel):
    title: str
    target_cloud: str # AWS, GCP, Azure, AliCloud, OVH, Multi-Cloud
    llm_provider: Optional[str] = "google"
    input_modality: Optional[str] = "text" # text, excel, pdf, word
    input_text: str
    input_filename: Optional[str] = None
    workload_type: Optional[str] = "Microservices & Web Apps"
    high_availability: Optional[str] = "Multi-AZ"
    compliance: Optional[str] = "Standard"
    budget_tier: Optional[str] = "Mid-Market"

@router.post("/extract-file")
async def extract_file_content(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """Upload an Excel, PDF, Word, or text file to extract content and preview metadata."""
    try:
        content_bytes = await file.read()
        filename = file.filename or "uploaded_document"
        result = extract_input_document(content_bytes, filename)
        return result
    except Exception as e:
        logger.error(f"Error parsing uploaded file: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to extract text from file: {str(e)}")

@router.post("/propose")
async def propose_architecture(
    req: ProposeArchitectureRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Propose target cloud architecture based on text input or extracted document content."""
    if not req.title or not req.title.strip():
        raise HTTPException(status_code=400, detail="Architecture title is required.")
    if not req.target_cloud or not req.target_cloud.strip():
        raise HTTPException(status_code=400, detail="Target Cloud Provider is required.")
    if not req.input_text or not req.input_text.strip():
        raise HTTPException(status_code=400, detail="Target architecture input/requirements text is required.")

    provider_name = req.llm_provider or "google"
    llm = LLMRouter.get_llm(provider=provider_name)
    builder = CloudArchitectureBuilder(llm=llm)

    proposal = await builder.propose_architecture(
        title=req.title.strip(),
        cloud_provider=req.target_cloud.strip(),
        input_text=req.input_text.strip(),
        workload_type=req.workload_type or "Microservices & Web Apps",
        high_availability=req.high_availability or "Multi-AZ",
        compliance=req.compliance or "Standard",
        budget_tier=req.budget_tier or "Mid-Market"
    )

    # Persist session in database
    session_id = str(uuid.uuid4())
    build_session = BuildArchitectureSession(
        id=session_id,
        title=req.title.strip(),
        target_cloud=req.target_cloud.strip(),
        llm_provider=provider_name,
        input_modality=req.input_modality or "text",
        input_text=req.input_text.strip(),
        input_filename=req.input_filename,
        workload_type=req.workload_type or "Microservices & Web Apps",
        high_availability=req.high_availability or "Multi-AZ",
        compliance=req.compliance or "Standard",
        budget_tier=req.budget_tier or "Mid-Market",
        status="completed",
        diagram_mermaid=proposal.get("diagram_mermaid", ""),
        diagram_drawio_xml=proposal.get("diagram_drawio_xml", ""),
        components_json=json.dumps(proposal.get("components", [])),
        tad_json=json.dumps(proposal),
        full_tad_markdown=proposal.get("full_tad_markdown", ""),
        total_monthly_cost_usd=float(proposal.get("total_estimated_monthly_usd", 0.0)),
        created_by_id=current_user.id
    )

    db.add(build_session)
    db.commit()
    db.refresh(build_session)

    return {
        "id": build_session.id,
        "title": build_session.title,
        "target_cloud": build_session.target_cloud,
        "llm_provider": build_session.llm_provider,
        "workload_type": build_session.workload_type,
        "high_availability": build_session.high_availability,
        "compliance": build_session.compliance,
        "budget_tier": build_session.budget_tier,
        "total_estimated_monthly_usd": build_session.total_monthly_cost_usd,
        "components": proposal.get("components", []),
        "diagram_mermaid": proposal.get("diagram_mermaid", ""),
        "diagram_drawio_xml": proposal.get("diagram_drawio_xml", ""),
        "full_tad_markdown": proposal.get("full_tad_markdown", ""),
        "executive_summary": proposal.get("executive_summary", ""),
        "cost_drivers_summary": proposal.get("cost_drivers_summary", ""),
        "created_at": build_session.created_at.isoformat()
    }

@router.post("/propose-file")
async def propose_architecture_with_file(
    title: str = Form(...),
    target_cloud: str = Form(...),
    llm_provider: Optional[str] = Form("google"),
    workload_type: Optional[str] = Form("Microservices & Web Apps"),
    high_availability: Optional[str] = Form("Multi-AZ"),
    compliance: Optional[str] = Form("Standard"),
    budget_tier: Optional[str] = Form("Mid-Market"),
    additional_notes: Optional[str] = Form(""),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Propose target cloud architecture with direct multipart file upload (Excel/PDF/Word)."""
    if not title or not title.strip():
        raise HTTPException(status_code=400, detail="Architecture title is required.")
    
    content_bytes = await file.read()
    filename = file.filename or "uploaded_document"
    doc_info = extract_input_document(content_bytes, filename)
    extracted_text = doc_info.get("extracted_text", "")

    if additional_notes and additional_notes.strip():
        combined_text = f"Additional Architecture Directives:\n{additional_notes.strip()}\n\nExtracted File Specifications ({filename}):\n{extracted_text}"
    else:
        combined_text = extracted_text

    llm = LLMRouter.get_llm(provider=llm_provider or "google")
    builder = CloudArchitectureBuilder(llm=llm)

    proposal = await builder.propose_architecture(
        title=title.strip(),
        cloud_provider=target_cloud.strip(),
        input_text=combined_text,
        workload_type=workload_type or "Microservices & Web Apps",
        high_availability=high_availability or "Multi-AZ",
        compliance=compliance or "Standard",
        budget_tier=budget_tier or "Mid-Market"
    )

    session_id = str(uuid.uuid4())
    build_session = BuildArchitectureSession(
        id=session_id,
        title=title.strip(),
        target_cloud=target_cloud.strip(),
        llm_provider=llm_provider or "google",
        input_modality=doc_info.get("modality", "document"),
        input_text=combined_text,
        input_filename=filename,
        workload_type=workload_type or "Microservices & Web Apps",
        high_availability=high_availability or "Multi-AZ",
        compliance=compliance or "Standard",
        budget_tier=budget_tier or "Mid-Market",
        status="completed",
        diagram_mermaid=proposal.get("diagram_mermaid", ""),
        diagram_drawio_xml=proposal.get("diagram_drawio_xml", ""),
        components_json=json.dumps(proposal.get("components", [])),
        tad_json=json.dumps(proposal),
        full_tad_markdown=proposal.get("full_tad_markdown", ""),
        total_monthly_cost_usd=float(proposal.get("total_estimated_monthly_usd", 0.0)),
        created_by_id=current_user.id
    )

    db.add(build_session)
    db.commit()
    db.refresh(build_session)

    return {
        "id": build_session.id,
        "title": build_session.title,
        "target_cloud": build_session.target_cloud,
        "llm_provider": build_session.llm_provider,
        "input_filename": filename,
        "workload_type": build_session.workload_type,
        "high_availability": build_session.high_availability,
        "compliance": build_session.compliance,
        "budget_tier": build_session.budget_tier,
        "total_estimated_monthly_usd": build_session.total_monthly_cost_usd,
        "components": proposal.get("components", []),
        "diagram_mermaid": proposal.get("diagram_mermaid", ""),
        "diagram_drawio_xml": proposal.get("diagram_drawio_xml", ""),
        "full_tad_markdown": proposal.get("full_tad_markdown", ""),
        "executive_summary": proposal.get("executive_summary", ""),
        "cost_drivers_summary": proposal.get("cost_drivers_summary", ""),
        "created_at": build_session.created_at.isoformat()
    }

@router.get("/sessions")
def list_build_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all past architecture build sessions."""
    sessions = db.query(BuildArchitectureSession).order_by(BuildArchitectureSession.created_at.desc()).all()
    return [{
        "id": s.id,
        "title": s.title,
        "target_cloud": s.target_cloud,
        "llm_provider": s.llm_provider,
        "input_modality": s.input_modality,
        "input_filename": s.input_filename,
        "workload_type": s.workload_type,
        "high_availability": s.high_availability,
        "compliance": s.compliance,
        "budget_tier": s.budget_tier,
        "total_estimated_monthly_usd": s.total_monthly_cost_usd,
        "created_at": s.created_at.isoformat()
    } for s in sessions]

@router.get("/sessions/{session_id}")
def get_build_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve full proposal, components table, diagram, and TAD for a build session."""
    session = db.query(BuildArchitectureSession).filter(BuildArchitectureSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Build architecture session not found.")

    comps = []
    if session.components_json:
        try:
            comps = json.loads(session.components_json)
        except Exception:
            comps = []

    tad_obj = {}
    if session.tad_json:
        try:
            tad_obj = json.loads(session.tad_json)
        except Exception:
            tad_obj = {}

    return {
        "id": session.id,
        "title": session.title,
        "target_cloud": session.target_cloud,
        "llm_provider": session.llm_provider,
        "input_modality": session.input_modality,
        "input_filename": session.input_filename,
        "input_text": session.input_text,
        "workload_type": session.workload_type,
        "high_availability": session.high_availability,
        "compliance": session.compliance,
        "budget_tier": session.budget_tier,
        "total_estimated_monthly_usd": session.total_monthly_cost_usd,
        "components": comps,
        "diagram_mermaid": session.diagram_mermaid,
        "diagram_drawio_xml": session.diagram_drawio_xml,
        "full_tad_markdown": session.full_tad_markdown,
        "executive_summary": tad_obj.get("executive_summary", ""),
        "cost_drivers_summary": tad_obj.get("cost_drivers_summary", ""),
        "created_at": session.created_at.isoformat()
    }

@router.get("/sessions/{session_id}/drawio")
def download_drawio_file(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Download Draw.io XML file for importing into diagrams.net or draw.io desktop."""
    session = db.query(BuildArchitectureSession).filter(BuildArchitectureSession.id == session_id).first()
    if not session or not session.diagram_drawio_xml:
        raise HTTPException(status_code=404, detail="Draw.io diagram not found for this session.")

    safe_title = "".join(c for c in session.title if c.isalnum() or c in (' ', '_', '-')).rstrip()
    safe_title = safe_title.replace(" ", "_") or "architecture"
    filename = f"{safe_title}_{session.target_cloud}.drawio"

    return Response(
        content=session.diagram_drawio_xml,
        media_type="application/xml",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )

@router.get("/sessions/{session_id}/tad")
def download_tad_markdown(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Download Technical Architecture Document in Markdown format."""
    session = db.query(BuildArchitectureSession).filter(BuildArchitectureSession.id == session_id).first()
    if not session or not session.full_tad_markdown:
        raise HTTPException(status_code=404, detail="TAD document not found for this session.")

    safe_title = "".join(c for c in session.title if c.isalnum() or c in (' ', '_', '-')).rstrip()
    safe_title = safe_title.replace(" ", "_") or "architecture"
    filename = f"TAD_{safe_title}_{session.target_cloud}.md"

    return PlainTextResponse(
        content=session.full_tad_markdown,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )

@router.delete("/sessions/{session_id}")
def delete_build_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete an architecture build session."""
    session = db.query(BuildArchitectureSession).filter(BuildArchitectureSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Build architecture session not found.")
    db.delete(session)
    db.commit()
    return {"status": "deleted", "id": session_id}
