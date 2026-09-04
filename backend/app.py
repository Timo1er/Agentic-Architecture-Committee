import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import text
from backend.config import settings
from backend.db.database import engine, Base, SessionLocal
from backend.db.models import User, UserRole, ProviderConfig, SSOConfig, GlobalInstruction, ArchitectureSource, BuildArchitectureSession
from backend.core.security import get_password_hash, encrypt_secret, is_bcrypt_hash
from backend.api.auth_routes import router as auth_router
from backend.api.admin_routes import router as admin_router
from backend.api.review_routes import router as review_router
from backend.api.feedback_routes import router as feedback_router
from backend.api.build_routes import router as build_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("arb.main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables
    logger.info("Initializing database tables...")
    Base.metadata.create_all(bind=engine)

    # Auto-migrate schema additions if needed
    try:
        with engine.connect() as conn:
            for col_stmt in [
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login_at timestamp without time zone",
                "ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS user_email character varying(255)",
                "ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS ip_address character varying(50)"
            ]:
                try:
                    conn.execute(text(col_stmt))
                    conn.commit()
                except Exception:
                    pass
    except Exception as e:
        logger.warning(f"Schema auto-migration notice: {e}")

    # Seed default Admin user if none exists
    db = SessionLocal()
    try:
        admin_user = db.query(User).filter(User.email == settings.ADMIN_EMAIL).first()
        if not admin_user:
            logger.info(f"Creating default Admin user: {settings.ADMIN_EMAIL}")
            admin_user = User(
                email=settings.ADMIN_EMAIL,
                hashed_password=get_password_hash(settings.ADMIN_PASSWORD),
                full_name="System Administrator",
                role=UserRole.ADMIN,
                is_active=True
            )
            db.add(admin_user)
        elif settings.RESET_ADMIN_PASSWORD or os.getenv("RESET_ADMIN_PASSWORD", "false").lower() in ("true", "1") or not is_bcrypt_hash(admin_user.hashed_password):
            logger.info(f"Resetting/upgrading Admin password hash to default for {settings.ADMIN_EMAIL}...")
            admin_user.hashed_password = get_password_hash(settings.ADMIN_PASSWORD)
            admin_user.is_active = True

        # Seed provider configs
        for p in ["google", "anthropic", "openai", "mistral", "aws", "mock"]:
            cfg = db.query(ProviderConfig).filter(ProviderConfig.provider_name == p).first()
            if not cfg:
                db.add(ProviderConfig(
                    provider_name=p,
                    is_enabled=True,
                    default_model="gemini-3.6-flash" if p == "google" else ("gpt-4o" if p == "openai" else ("claude-3-5-sonnet-20240620" if p == "anthropic" else None))
                ))
            elif p == "google" and (not cfg.default_model or cfg.default_model in ["gemini-1.5-pro", "gemini-1.5-flash", "gemini-2.5-flash", "gemini-2.5-pro", "gemini-pro", "gemini-flash-latest", "gemini-3.8-flash"]):
                cfg.default_model = "gemini-3.6-flash"

        # Seed default guidelines if empty
        if db.query(GlobalInstruction).count() == 0:
            db.add(GlobalInstruction(
                title="Strict Multi-Cloud High Availability & Zero Trust",
                content="All architectures spanning AWS, GCP, Azure, AliCloud, or OVH must enforce private database subnets, customer-managed KMS encryption, and multi-region failover provisions.",
                category="security"
            ))

        # Seed default architecture reference sources if empty
        if db.query(ArchitectureSource).count() == 0:
            db.add(ArchitectureSource(
                name="AWS & Multi-Cloud Well-Architected Framework",
                source_type="url",
                target_agent="global",
                url="https://aws.amazon.com/architecture/well-architected/",
                description="Comprehensive multi-cloud tenets for security, reliability, and operational excellence.",
                extracted_text="Design Principles: Stop guessing capacity needs, test systems at production scale, automate to make architectural experimentation easier, allow for evolutionary architectures, drive architectures using data, and improve through game days.",
                is_active=True
            ))
            db.add(ArchitectureSource(
                name="CIS Multi-Cloud Benchmark Standards",
                source_type="url",
                target_agent="secops_compliance",
                url="https://www.cisecurity.org/benchmark",
                description="Security baseline configurations and zero-trust controls across AWS, GCP, Azure, AliCloud, and OVH.",
                extracted_text="CIS Cloud Benchmark v3.0: Enforce customer-managed keys (CMEK) for all data stores, require TLS 1.3 in transit, restrict default security groups, and disable public IP assignment on database subnets.",
                is_active=True
            ))
            db.add(ArchitectureSource(
                name="Enterprise FinOps Cloud Rate Card 2026",
                source_type="excel",
                target_agent="finops",
                filename="enterprise_finops_rates_2026.xlsx",
                description="Negotiated enterprise discount tiers (EDP) and reserved capacity unit rates.",
                extracted_text="Enterprise Discount Schedules: AWS EDP Tier-2 32% discount on compute, GCP CUD 28% commitment discount, Azure Reserved 35% discount. Object storage tier 1 baseline: $0.015/GB/month across all regions.",
                is_active=True
            ))
            db.add(ArchitectureSource(
                name="Enterprise Microservices & ADR Standard",
                source_type="word",
                target_agent="lead_architect",
                filename="enterprise_adr_standard.docx",
                description="Corporate architectural standards for domain boundaries, event-driven integration, and ADR formatting.",
                extracted_text="Corporate ADR Mandate: Every microservice domain must document bounded contexts, declare sync vs async integration boundaries, and provide an outbox pattern implementation for distributed event publishing.",
                is_active=True
            ))

        db.commit()
    except Exception as e:
        logger.error(f"Error during database startup seed: {e}")
        db.rollback()
    finally:
        db.close()

    yield
    logger.info("Shutting down Architecture Review Board backend.")

app = FastAPI(
    title=settings.APP_NAME,
    description="Enterprise Multi-Agent Architecture Review Board across AWS, GCP, Azure, AliCloud, and OVH",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(review_router)
app.include_router(feedback_router)
app.include_router(build_router)

@app.get("/api/health")
def health_check():
    from backend.core.llm_router import LLMRouter
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "supported_clouds": ["AWS", "GCP", "Azure", "AliCloud", "OVH"],
        "supported_providers": ["Google", "Anthropic", "OpenAI", "Mistral", "AWS Bedrock", "Mock"],
        "active_providers": LLMRouter.get_active_providers()
    }

# Mount Static Frontend
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "static")
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

    @app.get("/")
    def serve_ui():
        return FileResponse(os.path.join(frontend_dir, "index.html"))

    @app.get("/{full_path:path}")
    def catch_all(full_path: str):
        if full_path.startswith("api/"):
            return JSONResponse(status_code=404, content={"detail": "API endpoint not found"})
        return FileResponse(os.path.join(frontend_dir, "index.html"))
