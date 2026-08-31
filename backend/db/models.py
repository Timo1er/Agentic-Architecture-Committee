import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Text, Boolean, Integer, Float, DateTime, ForeignKey, Enum as SQLEnum
)
from sqlalchemy.orm import relationship
import enum
from backend.db.database import Base

def generate_uuid():
    return str(uuid.uuid4())

class UserRole(str, enum.Enum):
    ADMIN = "Admin"
    REVIEWER = "Reviewer"

class ReviewStatus(str, enum.Enum):
    DRAFT = "draft"
    ANALYZING = "analyzing"
    AWAITING_HUMAN_VALIDATION = "awaiting_human_validation"
    APPROVED = "approved"
    REVISION_REQUESTED = "revision_requested"
    REJECTED = "rejected"

class FeedbackVerdict(str, enum.Enum):
    APPROVED = "approved"
    REVISION_REQUESTED = "revision_requested"
    REJECTED = "rejected"

class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    role = Column(SQLEnum(UserRole), default=UserRole.REVIEWER, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    reviews = relationship("ReviewSession", back_populates="creator")
    feedbacks = relationship("HumanFeedback", back_populates="reviewer")

class SSOConfig(Base):
    __tablename__ = "sso_configs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    provider_type = Column(String(50), default="local") # local, okta, saml
    is_enabled = Column(Boolean, default=False)
    client_id = Column(String(255), nullable=True)
    client_secret_encrypted = Column(Text, nullable=True)
    domain = Column(String(255), nullable=True)
    redirect_uri = Column(String(255), nullable=True)
    metadata_url = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class ProviderConfig(Base):
    __tablename__ = "provider_configs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    provider_name = Column(String(50), unique=True, nullable=False) # google, anthropic, openai, mistral, aws
    is_enabled = Column(Boolean, default=True)
    api_key_encrypted = Column(Text, nullable=True)
    default_model = Column(String(100), nullable=True)
    extra_config_json = Column(Text, nullable=True) # AWS region, Bedrock model id, etc.
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class GlobalInstruction(Base):
    __tablename__ = "global_instructions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    category = Column(String(100), default="general") # security, architecture, finops, general
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class ReviewSession(Base):
    __tablename__ = "review_sessions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    title = Column(String(255), nullable=False)
    status = Column(SQLEnum(ReviewStatus), default=ReviewStatus.DRAFT, nullable=False)
    target_clouds_json = Column(Text, nullable=False) # ["AWS", "GCP", "Azure", "AliCloud", "OVH"]
    llm_provider = Column(String(50), default="google")
    inputs_json = Column(Text, nullable=False) # raw diagram text, terraform code, service list
    created_by_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    creator = relationship("User", back_populates="reviews")
    adr = relationship("ArchitectureDecisionRecord", back_populates="review", uselist=False)
    feedbacks = relationship("HumanFeedback", back_populates="review")

class ArchitectureDecisionRecord(Base):
    __tablename__ = "adrs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    review_id = Column(String(36), ForeignKey("review_sessions.id"), nullable=False, unique=True)
    adr_number = Column(Integer, default=1)
    title = Column(String(255), nullable=False)
    status = Column(String(50), default="PROPOSED") # PROPOSED, ACCEPTED, REVISION_REQUIRED, REJECTED
    context = Column(Text, nullable=False)
    decision = Column(Text, nullable=False)
    consequences = Column(Text, nullable=False)
    risk_matrix_json = Column(Text, nullable=True) # list of risks with severity, impact, mitigation
    cost_breakdown_json = Column(Text, nullable=True) # cost estimates per cloud & service
    alternatives_json = Column(Text, nullable=True) # rejected alternatives & rationale
    full_markdown = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    review = relationship("ReviewSession", back_populates="adr")

class HumanFeedback(Base):
    __tablename__ = "human_feedbacks"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    review_id = Column(String(36), ForeignKey("review_sessions.id"), nullable=False)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    rating = Column(Integer, nullable=False) # 1 to 5 stars
    verdict = Column(SQLEnum(FeedbackVerdict), nullable=False)
    comments = Column(Text, nullable=True)
    corrections = Column(Text, nullable=True) # specific architecture edits / guidelines
    is_indexed_in_vector_db = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    review = relationship("ReviewSession", back_populates="feedbacks")
    reviewer = relationship("User", back_populates="feedbacks")

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)
    details = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
