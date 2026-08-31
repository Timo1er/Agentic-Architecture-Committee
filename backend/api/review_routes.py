import json
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from backend.db.database import get_db
from backend.db.models import (
    ReviewSession, ArchitectureDecisionRecord, ReviewStatus, GlobalInstruction, User
)
from backend.api.auth_routes import get_current_user
from backend.parsers.diagram_parser import DiagramParser
from backend.parsers.terraform_parser import TerraformParser
from backend.parsers.services_parser import ServicesParser
from backend.orchestrator.graph import arb_graph

router = APIRouter(prefix="/api/reviews", tags=["Architecture Reviews"])

class StartReviewRequest(BaseModel):
    title: str
    target_clouds: List[str] # ["AWS", "GCP", "Azure", "AliCloud", "OVH"]
    llm_provider: Optional[str] = "google"
    diagram_text: Optional[str] = None
    diagram_format: Optional[str] = "mermaid" # mermaid, drawio, image, pdf
    diagram_mime_type: Optional[str] = None
    diagram_filename: Optional[str] = None
    terraform_code: Optional[str] = None
    services_text: Optional[str] = None

class HumanValidationRequest(BaseModel):
    verdict: str # "approved", "revision_requested", "rejected"
    rating: Optional[int] = 5 # 1 to 5
    comments: Optional[str] = None
    corrections: Optional[str] = None

@router.post("")
async def start_review(
    req: StartReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Start an end-to-end multi-agent architecture review."""
    # 1. Parse all provided inputs
    parsed_inputs = {}
    if req.diagram_text:
        parsed_inputs["diagram"] = DiagramParser.parse(
            req.diagram_text,
            input_format=req.diagram_format or "mermaid",
            mime_type=req.diagram_mime_type,
            filename=req.diagram_filename
        )
    if req.terraform_code:
        parsed_inputs["terraform"] = TerraformParser.parse_hcl(req.terraform_code)
    if req.services_text:
        parsed_inputs["services"] = ServicesParser.parse_text(req.services_text)

    # 2. Gather active global guidelines
    active_guidelines = db.query(GlobalInstruction).filter(GlobalInstruction.is_active == True).all()
    guidelines_text = "\n".join([f"- {g.title}: {g.content}" for g in active_guidelines]) if active_guidelines else "Follow standard Well-Architected and CIS benchmarks."

    # 3. Create Review Session in DB
    session = ReviewSession(
        title=req.title,
        status=ReviewStatus.ANALYZING,
        target_clouds_json=json.dumps(req.target_clouds),
        llm_provider=req.llm_provider or "google",
        inputs_json=json.dumps(parsed_inputs),
        created_by_id=current_user.id
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    # 4. Prepare initial state for LangGraph
    initial_state = {
        "review_id": session.id,
        "title": req.title,
        "target_clouds": req.target_clouds,
        "llm_provider": req.llm_provider or "google",
        "model_name": None,
        "raw_inputs": parsed_inputs,
        "global_guidelines": guidelines_text,
        "memory_context": None,
        "lead_architect_output": None,
        "secops_output": None,
        "finops_output": None,
        "adr_output": None,
        "human_feedback": None,
        "status": "analyzing",
        "iteration_count": 0,
        "logs": [f"Initiating architecture evaluation for '{req.title}'."]
    }

    # 5. Execute LangGraph workflow
    final_state = await arb_graph.ainvoke(initial_state)

    # 6. Save generated ADR into DB
    adr_data = final_state.get("adr_output", {})
    adr_record = ArchitectureDecisionRecord(
        review_id=session.id,
        adr_number=adr_data.get("adr_number", 1),
        title=adr_data.get("adr_title", f"ADR-001: {req.title}"),
        status=adr_data.get("status", "PROPOSED"),
        context=adr_data.get("context", "Architecture context analysis"),
        decision=adr_data.get("decision", "Architecture evaluated and decisions recorded"),
        consequences=json.dumps(adr_data.get("consequences", {})),
        risk_matrix_json=json.dumps(adr_data.get("risk_matrix", [])),
        cost_breakdown_json=json.dumps(adr_data.get("cost_breakdown", {})),
        alternatives_json=json.dumps(adr_data.get("alternatives_considered", [])),
        full_markdown=adr_data.get("full_markdown_adr", "")
    )
    db.add(adr_record)
    
    session.status = ReviewStatus.AWAITING_HUMAN_VALIDATION
    db.commit()
    db.refresh(session)

    return {
        "review_id": session.id,
        "status": session.status.value,
        "title": session.title,
        "lead_architect_output": final_state.get("lead_architect_output"),
        "secops_output": final_state.get("secops_output"),
        "finops_output": final_state.get("finops_output"),
        "adr": adr_data,
        "logs": final_state.get("logs", [])
    }

@router.get("/{review_id}")
def get_review(review_id: str, db: Session = Depends(get_db)):
    session = db.query(ReviewSession).filter(ReviewSession.id == review_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Review session not found")

    adr = db.query(ArchitectureDecisionRecord).filter(ArchitectureDecisionRecord.review_id == review_id).first()

    return {
        "id": session.id,
        "title": session.title,
        "status": session.status.value,
        "target_clouds": json.loads(session.target_clouds_json) if session.target_clouds_json else [],
        "llm_provider": session.llm_provider,
        "inputs": json.loads(session.inputs_json) if session.inputs_json else {},
        "created_at": session.created_at.isoformat(),
        "adr": {
            "title": adr.title if adr else None,
            "status": adr.status if adr else None,
            "context": adr.context if adr else None,
            "decision": adr.decision if adr else None,
            "consequences": json.loads(adr.consequences) if (adr and adr.consequences) else {},
            "risk_matrix": json.loads(adr.risk_matrix_json) if (adr and adr.risk_matrix_json) else [],
            "cost_breakdown": json.loads(adr.cost_breakdown_json) if (adr and adr.cost_breakdown_json) else {},
            "alternatives": json.loads(adr.alternatives_json) if (adr and adr.alternatives_json) else [],
            "full_markdown": adr.full_markdown if adr else None
        } if adr else None
    }

@router.get("")
def list_reviews(db: Session = Depends(get_db)):
    reviews = db.query(ReviewSession).order_by(ReviewSession.created_at.desc()).all()
    return [{
        "id": r.id,
        "title": r.title,
        "status": r.status.value,
        "target_clouds": json.loads(r.target_clouds_json) if r.target_clouds_json else [],
        "llm_provider": r.llm_provider,
        "created_at": r.created_at.isoformat()
    } for r in reviews]

@router.post("/{review_id}/validate")
async def submit_human_validation(
    review_id: str,
    req: HumanValidationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Human-in-the-loop validation endpoint for approving, rejecting, or requesting cyclical revisions."""
    session = db.query(ReviewSession).filter(ReviewSession.id == review_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Review session not found")

    adr = db.query(ArchitectureDecisionRecord).filter(ArchitectureDecisionRecord.review_id == review_id).first()
    verdict = req.verdict.lower()

    if verdict == "approved":
        session.status = ReviewStatus.APPROVED
        if adr:
            adr.status = "ACCEPTED"
        db.commit()
        return {"status": "approved", "review_id": review_id, "message": "Architecture review formally accepted."}

    elif verdict == "rejected":
        session.status = ReviewStatus.REJECTED
        if adr:
            adr.status = "REJECTED"
        db.commit()
        return {"status": "rejected", "review_id": review_id, "message": "Architecture review rejected with remarks."}

    elif verdict == "revision_requested":
        session.status = ReviewStatus.REVISION_REQUESTED
        db.commit()

        # Cyclical graph re-invocation with operator's feedback
        parsed_inputs = json.loads(session.inputs_json) if session.inputs_json else {}
        clouds = json.loads(session.target_clouds_json) if session.target_clouds_json else ["AWS"]

        state_for_revision = {
            "review_id": session.id,
            "title": session.title,
            "target_clouds": clouds,
            "llm_provider": session.llm_provider or "google",
            "model_name": None,
            "raw_inputs": parsed_inputs,
            "global_guidelines": None,
            "memory_context": None,
            "lead_architect_output": None,
            "secops_output": None,
            "finops_output": None,
            "adr_output": None,
            "human_feedback": {
                "verdict": "revision_requested",
                "rating": req.rating,
                "comments": req.comments,
                "corrections": req.corrections
            },
            "status": "analyzing",
            "iteration_count": 1,
            "logs": [f"Cyclical re-evaluation triggered by operator feedback: {req.comments}"]
        }

        final_state = await arb_graph.ainvoke(state_for_revision)
        adr_data = final_state.get("adr_output", {})

        if adr:
            adr.status = "REVISION_REQUIRED"
            adr.decision = adr_data.get("decision", adr.decision)
            adr.consequences = json.dumps(adr_data.get("consequences", {}))
            adr.risk_matrix_json = json.dumps(adr_data.get("risk_matrix", []))
            adr.cost_breakdown_json = json.dumps(adr_data.get("cost_breakdown", {}))
            adr.alternatives_json = json.dumps(adr_data.get("alternatives_considered", []))
            adr.full_markdown = adr_data.get("full_markdown_adr", "")
            db.commit()

        session.status = ReviewStatus.AWAITING_HUMAN_VALIDATION
        db.commit()

        return {
            "status": "revised",
            "review_id": review_id,
            "adr": adr_data,
            "logs": final_state.get("logs", [])
        }
    
    raise HTTPException(status_code=400, detail="Invalid verdict. Choose approved, revision_requested, or rejected.")
