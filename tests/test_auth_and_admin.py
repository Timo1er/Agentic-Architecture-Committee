import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.db.database import Base
from backend.db.models import User, UserRole, ProviderConfig, SSOConfig, GlobalInstruction
from backend.core.security import (
    get_password_hash, verify_password, create_access_token, decode_access_token,
    encrypt_secret, decrypt_secret
)

# Test SQLite in-memory DB
engine = create_engine("sqlite:///:memory:")
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

def test_password_hashing_and_jwt():
    raw_pwd = "SecurePassword123!"
    hashed = get_password_hash(raw_pwd)
    assert verify_password(raw_pwd, hashed)
    assert not verify_password("WrongPassword", hashed)

    token = create_access_token({"sub": "user-123", "role": "Admin"})
    payload = decode_access_token(token)
    assert payload["sub"] == "user-123"
    assert payload["role"] == "Admin"

def test_secret_encryption():
    secret_key = "sk-live-123456789-secret"
    encrypted = encrypt_secret(secret_key)
    assert encrypted != secret_key
    decrypted = decrypt_secret(encrypted)
    assert decrypted == secret_key

def test_user_roles_and_admin_settings():
    db = TestingSessionLocal()
    
    # Create Admin
    admin = User(email="admin@test.com", hashed_password="hashed_pwd", role=UserRole.ADMIN)
    reviewer = User(email="reviewer@test.com", hashed_password="hashed_pwd", role=UserRole.REVIEWER)
    db.add_all([admin, reviewer])
    db.commit()

    assert db.query(User).filter(User.role == UserRole.ADMIN).count() == 1
    assert db.query(User).filter(User.role == UserRole.REVIEWER).count() == 1

    # Provider Config
    provider = ProviderConfig(provider_name="google", is_enabled=True, api_key_encrypted=encrypt_secret("test-key"))
    db.add(provider)
    db.commit()

    saved_p = db.query(ProviderConfig).filter(ProviderConfig.provider_name == "google").first()
    assert saved_p.is_enabled is True
    assert decrypt_secret(saved_p.api_key_encrypted) == "test-key"

    # Global Instruction
    instr = GlobalInstruction(title="Zero Trust", content="Require mTLS everywhere", category="security")
    db.add(instr)
    db.commit()
    assert db.query(GlobalInstruction).count() == 1

    db.close()
