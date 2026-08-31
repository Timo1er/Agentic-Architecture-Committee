import pytest
from backend.memory.vector_store import VectorMemoryService

def test_vector_memory_indexing_and_search():
    memory = VectorMemoryService()

    # Index feedback
    success = memory.index_feedback(
        feedback_id="fb-101",
        review_id="rev-202",
        title="High Throughput Payment Engine",
        verdict="revision_requested",
        rating=3,
        comments="Too expensive on Egress",
        corrections="Use OVH regional object storage or AWS Direct Connect for lower bandwidth fees.",
        target_clouds=["AWS", "OVH"]
    )
    assert success is True

    # Search for similar topology
    hits = memory.search_relevant_feedback("Payment Engine bandwidth costs", limit=2)
    assert len(hits) >= 1
    top_hit = hits[0]["payload"]
    assert top_hit["feedback_id"] == "fb-101"
    assert "Direct Connect" in top_hit["corrections"]

    # Format context string
    formatted_ctx = memory.format_memory_context("Payment Engine")
    assert "Historical Architectural Lessons" in formatted_ctx
    assert "Direct Connect" in formatted_ctx
