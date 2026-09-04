import io
import json
import xml.etree.ElementTree as ET
import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.config import settings
from backend.core.drawio_generator import DrawIOGenerator
from backend.core.source_extractor import extract_input_document, extract_source_content
from backend.agents.builder_agents import CloudArchitectureBuilder
from backend.core.llm_router import MockFallbackLLM

client = TestClient(app)

@pytest.fixture(scope="module")
def auth_token():
    res = client.post("/api/auth/login", json={
        "email": settings.ADMIN_EMAIL,
        "password": settings.ADMIN_PASSWORD
    })
    assert res.status_code == 200, f"Login failed: {res.text}"
    return res.json()["access_token"]

def test_drawio_generator_produces_valid_xml():
    """Test DrawIOGenerator generates well-formed Draw.io XML with tiers and components."""
    sample_components = [
        {
            "name": "CloudFront & WAF",
            "tier": "Edge & Ingress",
            "cloud_service": "Amazon CloudFront + AWS WAF",
            "sizing": "Anycast Global Edge",
            "purpose": "Terminates TLS and mitigates DDoS",
            "monthly_cost_usd": 120.0
        },
        {
            "name": "App Microservices",
            "tier": "Application / Compute",
            "cloud_service": "Amazon ECS (Fargate)",
            "sizing": "8x vCPU / 32GB RAM",
            "purpose": "Executes domain microservices",
            "monthly_cost_usd": 450.0
        },
        {
            "name": "Transactional DB",
            "tier": "Database & State",
            "cloud_service": "Amazon Aurora PostgreSQL",
            "sizing": "Multi-AZ Serverless v2",
            "purpose": "Primary ACID datastore",
            "monthly_cost_usd": 380.0
        }
    ]

    for cloud in ["AWS", "GCP", "Azure", "AliCloud", "OVH"]:
        xml_content = DrawIOGenerator.generate_xml(
            title=f"Test Architecture for {cloud}",
            cloud_provider=cloud,
            components=sample_components
        )
        assert xml_content.startswith('<?xml version="1.0" encoding="UTF-8"?>')
        assert '<mxfile' in xml_content
        assert '<diagram' in xml_content
        assert '<mxGraphModel' in xml_content
        assert f"Target Cloud: {cloud}" in xml_content

        root = ET.fromstring(xml_content)
        assert root.tag == "mxfile"
        diagram = root.find("diagram")
        assert diagram is not None
        model = diagram.find("mxGraphModel")
        assert model is not None
        root_cell = model.find("root")
        assert root_cell is not None

def test_source_extractor_text_and_documents():
    """Test source extraction functions for text, csv, and document dispatch."""
    raw_csv = b"Server Name,vCPU,RAM_GB,OS\nweb-app-01,4,16,Ubuntu 22.04\ndb-master,16,64,RHEL 8"
    extracted_csv = extract_source_content(source_type="excel", file_bytes=raw_csv, filename="inventory.csv")
    assert "web-app-01" in extracted_csv
    assert "db-master" in extracted_csv

    doc_info = extract_input_document(file_bytes=raw_csv, filename="servers.csv")
    assert doc_info["filename"] == "servers.csv"
    assert doc_info["char_count"] > 0
    assert "web-app-01" in doc_info["extracted_text"]

def test_builder_smart_fallback_matrix():
    """Test smart fallback covers all 5 major cloud providers with complete component schemas."""
    mock_llm = MockFallbackLLM()
    builder = CloudArchitectureBuilder(llm=mock_llm)

    for cloud in ["AWS", "GCP", "Azure", "AliCloud", "OVH"]:
        proposal = builder.get_smart_fallback(
            title=f"Enterprise {cloud} Workload",
            cloud_provider=cloud,
            input_text="10 virtual machines, 1TB database, Redis cache, high traffic API",
            workload_type="Microservices & Web Apps",
            high_availability="Multi-AZ",
            compliance="Standard",
            budget_tier="Mid-Market"
        )

        assert proposal["target_cloud"] == cloud
        assert len(proposal["components"]) >= 6
        assert proposal["total_estimated_monthly_usd"] > 0
        assert "diagram_mermaid" in proposal
        assert "diagram_drawio_xml" in proposal
        assert "full_tad_markdown" in proposal

        for c in proposal["components"]:
            assert "name" in c
            assert "tier" in c
            assert "cloud_service" in c
            assert "sizing" in c
            assert "purpose" in c
            assert "ha_resilience" in c
            assert "security_networking" in c
            assert "monthly_cost_usd" in c

def test_api_extract_file(auth_token):
    """Test POST /api/build/extract-file with a multipart document."""
    headers = {"Authorization": f"Bearer {auth_token}"}
    fake_file = io.BytesIO(b"Host: app-server-01\nCPU: 8 cores\nRAM: 32 GB\nStorage: 500GB SSD\nWorkload: Payment processing API")
    files = {"file": ("requirements.txt", fake_file, "text/plain")}

    res = client.post("/api/build/extract-file", headers=headers, files=files)
    assert res.status_code == 200
    data = res.json()
    assert data["filename"] == "requirements.txt"
    assert "app-server-01" in data["extracted_text"]
    assert data["char_count"] > 0

def test_api_propose_architecture_lifecycle(auth_token):
    """Test end-to-end proposal creation, retrieval, file exports, and deletion."""
    headers = {"Authorization": f"Bearer {auth_token}"}

    payload = {
        "title": "Automated Test Core Payment Platform",
        "target_cloud": "AWS",
        "llm_provider": "mock",
        "input_modality": "text",
        "input_text": "Decompose on-premise Java payment monolith into AWS microservices with multi-AZ Aurora PostgreSQL database and SQS decoupling.",
        "workload_type": "Core Financial & Payment",
        "high_availability": "Multi-AZ",
        "compliance": "PCI-DSS Level 1",
        "budget_tier": "Mid-Market"
    }

    res_prop = client.post("/api/build/propose", headers=headers, json=payload)
    assert res_prop.status_code == 200, f"Propose failed: {res_prop.text}"
    prop_data = res_prop.json()
    session_id = prop_data["id"]
    assert session_id is not None
    assert prop_data["target_cloud"] == "AWS"
    assert len(prop_data["components"]) > 0
    assert prop_data["total_estimated_monthly_usd"] > 0
    assert "diagram_mermaid" in prop_data
    assert "diagram_drawio_xml" in prop_data
    assert "<mxfile" in prop_data["diagram_drawio_xml"]

    res_list = client.get("/api/build/sessions", headers=headers)
    assert res_list.status_code == 200
    sessions = res_list.json()
    assert any(s["id"] == session_id for s in sessions)

    res_get = client.get(f"/api/build/sessions/{session_id}", headers=headers)
    assert res_get.status_code == 200
    detail = res_get.json()
    assert detail["id"] == session_id
    assert detail["title"] == payload["title"]
    assert len(detail["components"]) == len(prop_data["components"])

    res_drawio = client.get(f"/api/build/sessions/{session_id}/drawio", headers=headers)
    assert res_drawio.status_code == 200
    assert "application/xml" in res_drawio.headers.get("content-type", "")
    assert '<mxfile' in res_drawio.text

    res_tad = client.get(f"/api/build/sessions/{session_id}/tad", headers=headers)
    assert res_tad.status_code == 200
    assert "Technical Architecture Document" in res_tad.text
    assert "AWS" in res_tad.text

    res_del = client.delete(f"/api/build/sessions/{session_id}", headers=headers)
    assert res_del.status_code == 200
    assert res_del.json()["status"] == "deleted"

    res_get_after = client.get(f"/api/build/sessions/{session_id}", headers=headers)
    assert res_get_after.status_code == 404
