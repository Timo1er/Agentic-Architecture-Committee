import pytest
import asyncio
from backend.core.llm_router import LLMRouter
from backend.agents.lead_architect import LeadArchitectAgent
from backend.agents.secops_compliance import SecOpsComplianceAgent
from backend.agents.finops import FinOpsAgent
from backend.agents.synthesis_validator import SynthesisValidatorAgent

@pytest.mark.asyncio
async def test_lead_architect_agent():
    llm = LLMRouter.get_llm("google")
    agent = LeadArchitectAgent(llm)
    result = await agent.execute_analysis({
        "architecture_title": "Payment Ingestion Service",
        "target_clouds": ["AWS", "OVH"],
        "inputs": {"services": ["AWS EKS", "AWS Aurora", "OVH Redis"]}
    })
    assert result is not None
    assert result.get("role") == "Lead Architect" or "patterns_identified" in result

@pytest.mark.asyncio
async def test_secops_agent():
    llm = LLMRouter.get_llm("anthropic")
    agent = SecOpsComplianceAgent(llm)
    result = await agent.execute_analysis({
        "architecture_title": "Healthcare Portal",
        "target_clouds": ["GCP", "OVH"],
        "inputs": {"services": ["Cloud Run", "Cloud SQL"]}
    })
    assert result is not None
    assert result.get("role") == "SecOps & Compliance" or "owasp_compliance_score" in result

@pytest.mark.asyncio
async def test_finops_agent():
    llm = LLMRouter.get_llm("openai")
    agent = FinOpsAgent(llm)
    result = await agent.execute_analysis({
        "architecture_title": "E-Commerce App",
        "target_clouds": ["AWS", "Azure"],
        "inputs": {"services": ["AWS ECS", "Azure Cosmos DB"]}
    })
    assert result is not None
    assert "estimated_monthly_cost_usd" in result or "cost_breakdown" in result

@pytest.mark.asyncio
async def test_synthesis_validator_agent():
    llm = LLMRouter.get_llm("mistral")
    agent = SynthesisValidatorAgent(llm)
    result = await agent.execute_analysis({
        "architecture_title": "Enterprise Data Hub",
        "target_clouds": ["AWS", "GCP", "AliCloud"],
        "inputs": {"services": ["AWS S3", "GCP BigQuery", "AliCloud OSS"]}
    })
    assert result is not None
    md = agent.generate_markdown(result, {})
    assert "# " in md
    assert "Context" in md
