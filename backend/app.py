import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from backend.config import settings
from backend.db.database import engine, Base, SessionLocal
from backend.db.models import User, UserRole, ProviderConfig, SSOConfig, GlobalInstruction
from backend.core.security import get_password_hash, encrypt_secret
from backend.api.auth_routes import router as auth_router
from backend.api.admin_routes import router as admin_router
from backend.api.review_routes import router as review_router
from backend.api.feedback_routes import router as feedback_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("arb.main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables
    logger.info("Initializing database tables...")
    Base.metadata.create_all(bind=engine)

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

        # Seed provider configs
        for p in ["google", "anthropic", "openai", "mistral", "aws"]:
            cfg = db.query(ProviderConfig).filter(ProviderConfig.provider_name == p).first()
            if not cfg:
                db.add(ProviderConfig(
                    provider_name=p,
                    is_enabled=True,
                    default_model="gemini-1.5-pro" if p == "google" else ("gpt-4o" if p == "openai" else ("claude-3-5-sonnet-20240620" if p == "anthropic" else None))
                ))

        # Seed default guidelines if empty
        if db.query(GlobalInstruction).count() == 0:
            db.add(GlobalInstruction(
                title="Strict Multi-Cloud High Availability & Zero Trust",
                content="All architectures spanning AWS, GCP, Azure, AliCloud, or OVH must enforce private database subnets, customer-managed KMS encryption, and multi-region failover provisions.",
                category="security"
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

@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "supported_clouds": ["AWS", "GCP", "Azure", "AliCloud", "OVH"],
        "supported_providers": ["Google", "Anthropic", "OpenAI", "Mistral", "AWS Bedrock"]
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
