import pytest
from fastapi.testclient import TestClient
from backend.app import app
from backend.core.security import (
    get_password_hash, verify_password, validate_password_strength,
    create_access_token, decode_access_token, is_bcrypt_hash
)
from backend.config import settings
from backend.db.database import SessionLocal
from backend.db.models import User, UserRole, AuditLog

client = TestClient(app)

@pytest.fixture(scope="module")
def admin_token():
    res = client.post("/api/auth/login", json={
        "email": settings.ADMIN_EMAIL,
        "password": settings.ADMIN_PASSWORD
    })
    assert res.status_code == 200
    return res.json()["access_token"]

def test_password_security_and_hashing():
    raw_pwd = "SecurePassword123!"
    hashed = get_password_hash(raw_pwd)
    
    assert is_bcrypt_hash(hashed)
    assert verify_password(raw_pwd, hashed) is True
    assert verify_password("WrongPassword123!", hashed) is False
    assert verify_password("", hashed) is False
    assert verify_password(raw_pwd, "") is False

def test_password_strength_validator():
    assert validate_password_strength("short") is not None
    assert validate_password_strength("12345678") is not None # no letters
    assert validate_password_strength("abcdefgh") is not None # no digits
    assert validate_password_strength("ValidPass123!") is None

def test_unauthenticated_requests_rejected():
    res_me = client.get("/api/auth/me")
    assert res_me.status_code == 401

    res_admin = client.get("/api/admin/users")
    assert res_admin.status_code == 401

    res_stats = client.get("/api/admin/stats")
    assert res_stats.status_code == 401

def test_admin_login_and_me(admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    res = client.get("/api/auth/me", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["email"] == settings.ADMIN_EMAIL
    assert data["role"] == "Admin"
    assert data["is_active"] is True

def test_user_registration_and_rbac(admin_token):
    test_email = "test.reviewer@company.com"
    test_password = "ReviewerPass123!"

    # 1. Register new user
    res_reg = client.post("/api/auth/register", json={
        "email": test_email,
        "password": test_password,
        "full_name": "Test Reviewer"
    })
    assert res_reg.status_code == 200
    reg_data = res_reg.json()
    assert "access_token" in reg_data
    reviewer_token = reg_data["access_token"]
    assert reg_data["user"]["role"] == "Reviewer"

    # 2. Duplicate registration should fail
    res_dup = client.post("/api/auth/register", json={
        "email": test_email,
        "password": test_password
    })
    assert res_dup.status_code == 400

    # 3. Reviewer cannot access admin endpoints
    rev_headers = {"Authorization": f"Bearer {reviewer_token}"}
    res_forbidden = client.get("/api/admin/users", headers=rev_headers)
    assert res_forbidden.status_code == 403

    res_forbidden_stats = client.get("/api/admin/stats", headers=rev_headers)
    assert res_forbidden_stats.status_code == 403

    # 4. Reviewer can change their password
    res_cp = client.post("/api/auth/change-password", headers=rev_headers, json={
        "current_password": test_password,
        "new_password": "NewSecretPass456!"
    })
    assert res_cp.status_code == 200

    # 5. Clean up test user
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    user_id = reg_data["user"]["id"]
    res_del = client.delete(f"/api/admin/users/{user_id}", headers=admin_headers)
    assert res_del.status_code == 200

def test_admin_user_lifecycle_and_audit(admin_token):
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    lifecycle_email = "lifecycle.user@company.com"
    initial_pwd = "InitPassword123!"

    # 1. Admin creates user
    res_create = client.post("/api/admin/users", headers=admin_headers, json={
        "email": lifecycle_email,
        "password": initial_pwd,
        "full_name": "Lifecycle Tester",
        "role": "Reviewer",
        "is_active": True
    })
    assert res_create.status_code == 200
    created_user = res_create.json()["user"]
    user_id = created_user["id"]

    # 2. Admin lists users with search filter
    res_list = client.get(f"/api/admin/users?search=lifecycle", headers=admin_headers)
    assert res_list.status_code == 200
    users_found = res_list.json()
    assert len(users_found) >= 1
    assert any(u["id"] == user_id for u in users_found)

    # 3. Admin updates user details
    res_update = client.put(f"/api/admin/users/{user_id}", headers=admin_headers, json={
        "full_name": "Updated Lifecycle Tester",
        "role": "Reviewer"
    })
    assert res_update.status_code == 200
    assert res_update.json()["user"]["full_name"] == "Updated Lifecycle Tester"

    # 4. Admin deactivates user
    res_deact = client.put(f"/api/admin/users/{user_id}/status", headers=admin_headers, json={
        "is_active": False
    })
    assert res_deact.status_code == 200

    # 5. Deactivated user cannot log in
    res_blocked = client.post("/api/auth/login", json={
        "email": lifecycle_email,
        "password": initial_pwd
    })
    assert res_blocked.status_code == 403

    # 6. Admin re-activates user
    res_react = client.put(f"/api/admin/users/{user_id}/status", headers=admin_headers, json={
        "is_active": True
    })
    assert res_react.status_code == 200

    # 7. Admin resets user password
    new_pwd = "ResetPass789!"
    res_reset = client.post(f"/api/admin/users/{user_id}/reset-password", headers=admin_headers, json={
        "new_password": new_pwd
    })
    assert res_reset.status_code == 200

    # 8. User logs in with new password
    res_new_login = client.post("/api/auth/login", json={
        "email": lifecycle_email,
        "password": new_pwd
    })
    assert res_new_login.status_code == 200

    # 9. Check Audit Logs
    res_audit = client.get("/api/admin/audit-logs?limit=20", headers=admin_headers)
    assert res_audit.status_code == 200
    audit_logs = res_audit.json()
    actions = [l["action"] for l in audit_logs]
    assert "USER_CREATED" in actions
    assert "USER_STATUS_TOGGLED" in actions
    assert "PASSWORD_RESET_ADMIN" in actions

    # 10. Safety check: Admin cannot delete or deactivate themselves
    me = client.get("/api/auth/me", headers=admin_headers).json()
    res_self_del = client.delete(f"/api/admin/users/{me['id']}", headers=admin_headers)
    assert res_self_del.status_code == 400

    res_self_deact = client.put(f"/api/admin/users/{me['id']}/status", headers=admin_headers, json={"is_active": False})
    assert res_self_deact.status_code == 400

    # 11. Clean up
    res_del = client.delete(f"/api/admin/users/{user_id}", headers=admin_headers)
    assert res_del.status_code == 200

def test_guidelines_lifecycle_and_update(admin_token):
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. List guidelines
    res_list = client.get("/api/admin/guidelines", headers=admin_headers)
    assert res_list.status_code == 200
    initial_count = len(res_list.json())

    # 2. Create a new guideline
    res_create = client.post("/api/admin/guidelines", headers=admin_headers, json={
        "title": "FinOps Spot Instance Policy",
        "content": "All non-production batch workloads must leverage EC2 Spot or GCP Preemptible VMs.",
        "category": "finops",
        "is_active": True
    })
    assert res_create.status_code == 200
    created = res_create.json()
    assert created["status"] == "created"
    guideline_id = created["id"]
    assert created["title"] == "FinOps Spot Instance Policy"
    assert created["category"] == "finops"
    assert created["is_active"] is True

    # 3. Update the guideline (title, content, category)
    res_update = client.put(f"/api/admin/guidelines/{guideline_id}", headers=admin_headers, json={
        "title": "FinOps Spot & Graviton Policy",
        "content": "All batch workloads must leverage Spot VMs with ARM64/Graviton architectures.",
        "category": "finops"
    })
    assert res_update.status_code == 200
    updated = res_update.json()
    assert updated["status"] == "updated"
    assert updated["title"] == "FinOps Spot & Graviton Policy"
    assert "Graviton" in updated["content"]
    assert updated["is_active"] is True

    # 4. Toggle active status via PUT
    res_toggle = client.put(f"/api/admin/guidelines/{guideline_id}", headers=admin_headers, json={
        "is_active": False
    })
    assert res_toggle.status_code == 200
    assert res_toggle.json()["is_active"] is False

    # 5. Validation checks: empty title or content should fail with 400
    res_empty_title = client.put(f"/api/admin/guidelines/{guideline_id}", headers=admin_headers, json={
        "title": "   "
    })
    assert res_empty_title.status_code == 400

    res_empty_content = client.put(f"/api/admin/guidelines/{guideline_id}", headers=admin_headers, json={
        "content": ""
    })
    assert res_empty_content.status_code == 400

    # 6. Update non-existent guideline should return 404
    res_not_found = client.put("/api/admin/guidelines/non-existent-uuid-123", headers=admin_headers, json={
        "title": "Whatever"
    })
    assert res_not_found.status_code == 404

    # 7. Audit log verification
    res_audit = client.get("/api/admin/audit-logs?limit=20", headers=admin_headers)
    assert res_audit.status_code == 200
    actions = [l["action"] for l in res_audit.json()]
    assert "GUIDELINE_CREATED" in actions
    assert "GUIDELINE_UPDATED" in actions

    # 8. Clean up guideline
    res_del = client.delete(f"/api/admin/guidelines/{guideline_id}", headers=admin_headers)
    assert res_del.status_code == 200

    # 9. Verify deletion in list
    res_list_after = client.get("/api/admin/guidelines", headers=admin_headers)
    assert res_list_after.status_code == 200
    ids_after = [g["id"] for g in res_list_after.json()]
    assert guideline_id not in ids_after

def test_sources_lifecycle_and_agent_binding(admin_token):
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. List sources
    res_list = client.get("/api/admin/sources", headers=admin_headers)
    assert res_list.status_code == 200
    sources = res_list.json()
    assert isinstance(sources, list)

    # 2. Create URL source targeted to secops_compliance
    res_url = client.post("/api/admin/sources", headers=admin_headers, json={
        "name": "NIST CSF 2.0 Multi-Cloud Guidance",
        "source_type": "url",
        "target_agent": "secops_compliance",
        "url": "https://www.nist.gov/cyberframework",
        "description": "National security standards for cloud governance and identity federation.",
        "is_active": True
    })
    assert res_url.status_code == 200
    created_url = res_url.json()
    assert created_url["status"] == "created"
    url_source_id = created_url["id"]
    assert created_url["target_agent"] == "secops_compliance"
    assert created_url["source_type"] == "url"

    # 3. Create simulated file source (Excel) targeted to finops
    import io
    excel_content = b"PK\x03\x04simulated_xlsx_binary_data"
    res_file = client.post(
        "/api/admin/sources",
        headers=admin_headers,
        data={
            "name": "Q3 Enterprise Reserved Instance Pricing",
            "source_type": "excel",
            "target_agent": "finops",
            "description": "Negotiated EDP rates for compute and storage.",
            "is_active": "true"
        },
        files={"file": ("reserved_rates_q3.xlsx", io.BytesIO(excel_content), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    )
    assert res_file.status_code == 200
    created_file = res_file.json()
    assert created_file["status"] == "created"
    file_source_id = created_file["id"]
    assert created_file["target_agent"] == "finops"
    assert created_file["source_type"] == "excel"
    assert created_file["filename"] == "reserved_rates_q3.xlsx"

    # 4. Filter sources by target_agent
    res_filter_finops = client.get("/api/admin/sources?target_agent=finops", headers=admin_headers)
    assert res_filter_finops.status_code == 200
    assert any(s["id"] == file_source_id for s in res_filter_finops.json())

    # 5. Filter sources by source_type
    res_filter_url = client.get("/api/admin/sources?source_type=url", headers=admin_headers)
    assert res_filter_url.status_code == 200
    assert any(s["id"] == url_source_id for s in res_filter_url.json())

    # 6. Update URL source (change target to global and toggle inactive)
    res_update = client.put(f"/api/admin/sources/{url_source_id}", headers=admin_headers, json={
        "name": "NIST CSF 2.0 Enterprise Baseline",
        "target_agent": "global",
        "is_active": False
    })
    assert res_update.status_code == 200
    updated = res_update.json()
    assert updated["status"] == "updated"
    assert updated["name"] == "NIST CSF 2.0 Enterprise Baseline"
    assert updated["target_agent"] == "global"
    assert updated["is_active"] is False

    # 7. Audit logs contain SOURCE_CREATED and SOURCE_UPDATED
    res_audit = client.get("/api/admin/audit-logs?limit=25", headers=admin_headers)
    assert res_audit.status_code == 200
    actions = [l["action"] for l in res_audit.json()]
    assert "SOURCE_CREATED" in actions
    assert "SOURCE_UPDATED" in actions

    # 8. Clean up created sources
    res_del1 = client.delete(f"/api/admin/sources/{url_source_id}", headers=admin_headers)
    assert res_del1.status_code == 200
    res_del2 = client.delete(f"/api/admin/sources/{file_source_id}", headers=admin_headers)
    assert res_del2.status_code == 200


