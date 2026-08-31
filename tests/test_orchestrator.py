import pytest
from backend.orchestrator.graph import arb_graph

@pytest.mark.asyncio
async def test_langgraph_execution_cycle():
    state = {
        "review_id": "test-review-123",
        "title": "Real-Time Event Processing System",
        "target_clouds": ["AWS", "GCP", "OVH"],
        "llm_provider": "google",
        "model_name": None,
        "raw_inputs": {
            "services": ["AWS Lambda", "GCP PubSub", "OVH Managed Postgres"]
        },
        "global_guidelines": "Enforce zero trust and least-privilege IAM.",
        "memory_context": None,
        "lead_architect_output": None,
        "secops_output": None,
        "finops_output": None,
        "adr_output": None,
        "human_feedback": None,
        "status": "analyzing",
        "iteration_count": 0,
        "logs": []
    }

    # Execute workflow graph
    result = await arb_graph.ainvoke(state)
    assert result is not None
    assert result["status"] == "awaiting_human_validation"
    assert result["adr_output"] is not None
    assert "full_markdown_adr" in result["adr_output"]
    assert len(result["logs"]) >= 4

@pytest.mark.asyncio
async def test_cyclical_human_revision():
    # Simulate operator requesting revision
    state_with_feedback = {
        "review_id": "test-review-456",
        "title": "Payment Settlement Engine",
        "target_clouds": ["AWS", "Azure"],
        "llm_provider": "anthropic",
        "model_name": None,
        "raw_inputs": {"services": ["AWS ECS", "Azure SQL"]},
        "global_guidelines": None,
        "memory_context": None,
        "lead_architect_output": None,
        "secops_output": None,
        "finops_output": None,
        "adr_output": None,
        "human_feedback": {
            "verdict": "revision_requested",
            "rating": 3,
            "comments": "Need dedicated read-replicas for reporting",
            "corrections": "Add read-replica pool in private subnet"
        },
        "status": "analyzing",
        "iteration_count": 1,
        "logs": []
    }

    result = await arb_graph.ainvoke(state_with_feedback)
    assert result is not None
    assert result["adr_output"] is not None
