import pytest
from backend.parsers.diagram_parser import DiagramParser
from backend.parsers.terraform_parser import TerraformParser
from backend.parsers.services_parser import ServicesParser

def test_mermaid_diagram_parsing():
    mermaid_code = """
    graph TD
      Client[Web App] -->|HTTPS| Gateway[API Gateway]
      Gateway --> Auth[Auth Service]
      Gateway --> Orders[Order Service]
      Orders --> DB[(PostgreSQL)]
    """
    result = DiagramParser.parse_mermaid(mermaid_code)
    assert result["type"] == "mermaid"
    assert result["node_count"] >= 4
    assert result["edge_count"] >= 3
    node_labels = [n["label"] for n in result["nodes"]]
    assert any("Web App" in l for l in node_labels)
    assert any("API Gateway" in l for l in node_labels)

def test_drawio_xml_parsing():
    xml_data = """<mxGraphModel>
      <root>
        <mxCell id="0"/>
        <mxCell id="1" parent="0"/>
        <mxCell id="node1" value="EKS Cluster" parent="1"/>
        <mxCell id="node2" value="RDS Database" parent="1"/>
        <mxCell id="edge1" value="SQL Query" source="node1" target="node2" parent="1"/>
      </root>
    </mxGraphModel>"""
    result = DiagramParser.parse_drawio(xml_data)
    assert result["type"] == "drawio_xml"
    assert result["node_count"] == 2
    assert result["edge_count"] == 1
    assert result["nodes"][0]["label"] == "EKS Cluster"

def test_terraform_hcl_parsing():
    tf_code = """
    provider "aws" {
      region = "us-east-1"
    }

    resource "aws_s3_bucket" "data_bucket" {
      bucket = "my-enterprise-data-lake"
    }

    resource "google_compute_instance" "app_vm" {
      name = "gcp-worker"
    }
    """
    result = TerraformParser.parse_hcl(tf_code)
    assert result["type"] == "terraform"
    assert result["resource_count"] == 2
    clouds = [r["cloud"] for r in result["resources"]]
    assert "AWS" in clouds
    assert "GCP" in clouds

def test_services_list_parsing():
    services_text = """
    - AWS EKS Kubernetes Cluster
    - GCP BigQuery Data Warehouse
    - Azure Cosmos DB
    - OVH Managed Redis
    - AliCloud Object Storage OSS
    """
    result = ServicesParser.parse_text(services_text)
    assert result["type"] == "services_list"
    assert result["total_items"] == 5
    detected = result["detected_clouds"]
    assert "AWS" in detected
    assert "GCP" in detected
    assert "Azure" in detected
    assert "OVH" in detected
    assert "AliCloud" in detected

def test_image_diagram_parsing():
    mock_png_b64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    result = DiagramParser.parse(mock_png_b64, input_format="image", filename="arch_diagram.png")
    assert result["type"] == "image_diagram"
    assert result["mime_type"] == "image/png"
    assert result["has_multimodal_payload"] is True
    assert "raw_data_uri" in result

def test_pdf_diagram_parsing():
    mock_pdf_b64 = "data:application/pdf;base64,JVBERi0xLjQKJcTl8uXrp/Og0MTGCjQgMCBvYmoKPDwKL1R5cGUgL1BhZ2Vz"
    result = DiagramParser.parse(mock_pdf_b64, input_format="pdf", filename="system_design.pdf")
    assert result["type"] == "pdf_diagram"
    assert result["mime_type"] == "application/pdf"
    assert result["filename"] == "system_design.pdf"
