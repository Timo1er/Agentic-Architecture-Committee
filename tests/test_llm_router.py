import pytest
from backend.core.llm_router import LLMRouter, MockFallbackLLM

def test_llm_router_mock_fallback():
    # When keys are absent, router returns MockFallbackLLM
    for provider in ["google", "anthropic", "openai", "mistral", "aws"]:
        llm = LLMRouter.get_llm(provider=provider)
        assert llm is not None
        response = llm.invoke("Evaluate Lead Architect patterns for CQRS and Microservices.")
        assert response is not None
        assert hasattr(response, "content")
        assert len(response.content) > 0

def test_mock_llm_json_generation():
    llm = MockFallbackLLM(provider_name="google")
    res_lead = llm.invoke("Lead Architect evaluation")
    assert "patterns_identified" in res_lead.content

    res_sec = llm.invoke("SecOps and OWASP compliance")
    assert "owasp_compliance_score" in res_sec.content

    res_fin = llm.invoke("FinOps cost estimation")
    assert "estimated_monthly_cost_usd" in res_fin.content

    res_adr = llm.invoke("Synthesis and ADR generation")
    assert "ADR" in res_adr.content
