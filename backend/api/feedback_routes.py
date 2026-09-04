import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from backend.db.database import get_db
from backend.db.models import HumanFeedback, ReviewSession, FeedbackVerdict, User
from backend.api.auth_routes import get_current_user
from backend.memory.vector_store import vector_memory

router = APIRouter(prefix="/api/feedback", tags=["Continuous Learning & Feedback"])

class SubmitFeedbackRequest(BaseModel):
    review_id: str
    rating: int = Field(ge=1, le=5)
    verdict: FeedbackVerdict
    comments: Optional[str] = None
    corrections: Optional[str] = None

@router.post("")
def submit_feedback(
    req: SubmitFeedbackRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Submits operator feedback and automatically indexes corrections into Qdrant/vector store."""
    session = db.query(ReviewSession).filter(ReviewSession.id == req.review_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Review session not found")

    feedback = HumanFeedback(
        review_id=req.review_id,
        user_id=current_user.id,
        rating=req.rating,
        verdict=req.verdict,
        comments=req.comments,
        corrections=req.corrections,
        is_indexed_in_vector_db=False
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)

    # Automatically index into vector memory for continuous learning
    target_clouds = json.loads(session.target_clouds_json) if session.target_clouds_json else []
    success = vector_memory.index_feedback(
        feedback_id=feedback.id,
        review_id=session.id,
        title=session.title,
        verdict=req.verdict.value,
        rating=req.rating,
        comments=req.comments,
        corrections=req.corrections,
        target_clouds=target_clouds
    )

    if success:
        feedback.is_indexed_in_vector_db = True
        db.commit()

    return {
        "feedback_id": feedback.id,
        "review_id": session.id,
        "is_indexed_in_vector_db": feedback.is_indexed_in_vector_db,
        "message": "Feedback recorded and indexed into vector memory for continuous learning."
    }

@router.get("/history")
def list_feedback_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    feedbacks = db.query(HumanFeedback).order_by(HumanFeedback.created_at.desc()).all()
    results = []
    for f in feedbacks:
        review_title = f.review.title if f.review else "Unknown Review"
        results.append({
            "id": f.id,
            "review_id": f.review_id,
            "review_title": review_title,
            "rating": f.rating,
            "verdict": f.verdict.value,
            "comments": f.comments,
            "corrections": f.corrections,
            "is_indexed_in_vector_db": f.is_indexed_in_vector_db,
            "created_at": f.created_at.isoformat()
        })
    return results
