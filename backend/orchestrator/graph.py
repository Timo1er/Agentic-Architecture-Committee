import asyncio
import logging
from typing import Dict, Any, Literal
from langgraph.graph import StateGraph, END
from backend.orchestrator.state import ARBState
from backend.core.llm_router import LLMRouter
from backend.agents.lead_architect import LeadArchitectAgent
from backend.agents.secops_compliance import SecOpsComplianceAgent
from backend.agents.finops import FinOpsAgent
from backend.agents.synthesis_validator import SynthesisValidatorAgent
from backend.memory.vector_store import vector_memory

logger = logging.getLogger("arb.orchestrator")

async def ingest_and_retrieve_memory_node(state: ARBState) -> Dict[str, Any]:
    """Node: Retrieve relevant past human corrections and corporate guidelines."""
    query_text = f"{state['title']} {' '.join(state['target_clouds'])} {str(state['raw_inputs'])}"
    memory_ctx = vector_memory.format_memory_context(query_text)
    
    log_msg = f"Retrieved vector memory context for architecture '{state['title']}'."
    return {
        "memory_context": memory_ctx,
        "status": "analyzing",
        "iteration_count": state.get("iteration_count", 0) + 1,
        "logs": [log_msg]
    }

async def run_lead_architect_node(state: ARBState) -> Dict[str, Any]:
    """Node: Execute Lead Architect evaluation."""
    llm = LLMRouter.get_llm(provider=state.get("llm_provider"), model_name=state.get("model_name"))
    agent = LeadArchitectAgent(llm=llm)

    payload = {
        "architecture_title": state["title"],
        "target_clouds": state["target_clouds"],
        "inputs": state["raw_inputs"],
        "guidelines": state.get("global_guidelines"),
        "historical_lessons": state.get("memory_context"),
        "prior_human_feedback": state.get("human_feedback")
    }

    result = await agent.execute_analysis(payload)
    return {
        "lead_architect_output": result,
        "logs": [f"Lead Architect completed pattern analysis (Modularity Score: {result.get('modularity_score', 'N/A')})."]
    }

async def run_secops_node(state: ARBState) -> Dict[str, Any]:
    """Node: Execute SecOps & Compliance evaluation."""
    llm = LLMRouter.get_llm(provider=state.get("llm_provider"), model_name=state.get("model_name"))
    agent = SecOpsComplianceAgent(llm=llm)

    payload = {
        "architecture_title": state["title"],
        "target_clouds": state["target_clouds"],
        "inputs": state["raw_inputs"],
        "guidelines": state.get("global_guidelines"),
        "historical_lessons": state.get("memory_context"),
        "prior_human_feedback": state.get("human_feedback")
    }

    result = await agent.execute_analysis(payload)
    return {
        "secops_output": result,
        "logs": [f"SecOps Agent completed security & OWASP audit (Score: {result.get('owasp_compliance_score', 'N/A')})."]
    }

async def run_finops_node(state: ARBState) -> Dict[str, Any]:
    """Node: Execute FinOps & Capacity evaluation."""
    llm = LLMRouter.get_llm(provider=state.get("llm_provider"), model_name=state.get("model_name"))
    agent = FinOpsAgent(llm=llm)

    payload = {
        "architecture_title": state["title"],
        "target_clouds": state["target_clouds"],
        "inputs": state["raw_inputs"],
        "guidelines": state.get("global_guidelines"),
        "historical_lessons": state.get("memory_context"),
        "prior_human_feedback": state.get("human_feedback")
    }

    result = await agent.execute_analysis(payload)
    cost = result.get("estimated_monthly_cost_usd", "N/A")
    return {
        "finops_output": result,
        "logs": [f"FinOps Agent completed cost modeling (Estimated Monthly Cost: ${cost})."]
    }

async def run_synthesis_validator_node(state: ARBState) -> Dict[str, Any]:
    """Node: Synthesize findings into structured ADR."""
    llm = LLMRouter.get_llm(provider=state.get("llm_provider"), model_name=state.get("model_name"))
    agent = SynthesisValidatorAgent(llm=llm)

    payload = {
        "architecture_title": state["title"],
        "target_clouds": state["target_clouds"],
        "inputs": state["raw_inputs"],
        "lead_architect_findings": state.get("lead_architect_output"),
        "secops_findings": state.get("secops_output"),
        "finops_findings": state.get("finops_output"),
        "historical_lessons": state.get("memory_context"),
        "prior_human_feedback": state.get("human_feedback"),
        "iteration": state.get("iteration_count", 1)
    }

    result = await agent.execute_analysis(payload)
    
    # Ensure markdown representation is present
    if "full_markdown_adr" not in result or len(result["full_markdown_adr"]) < 50:
        result["full_markdown_adr"] = agent.generate_markdown(result, payload)

    return {
        "adr_output": result,
        "status": "awaiting_human_validation",
        "logs": [f"Validator Agent generated ADR '{result.get('adr_title', 'ADR-001')}' and entered Human Validation checkpoint."]
    }

def route_validation(state: ARBState) -> Literal["revision_loop", "finalize_approved", "finalize_rejected", "wait_for_human"]:
    """Conditional router based on Human Operator validation in the loop."""
    feedback = state.get("human_feedback")
    if not feedback:
        return "wait_for_human"

    verdict = feedback.get("verdict", "").lower()
    if verdict == "approved":
        return "finalize_approved"
    elif verdict == "rejected":
        return "finalize_rejected"
    elif verdict == "revision_requested":
        if state.get("iteration_count", 0) > 1:
            return "wait_for_human"
        return "revision_loop"
    
    return "wait_for_human"

async def finalize_approved_node(state: ARBState) -> Dict[str, Any]:
    return {
        "status": "approved",
        "logs": ["ADR has been formally approved by human operator."]
    }

async def finalize_rejected_node(state: ARBState) -> Dict[str, Any]:
    return {
        "status": "rejected",
        "logs": ["ADR was rejected by human operator. Rejection reasons recorded."]
    }

def build_arb_graph() -> StateGraph:
    """Constructs the cyclical LangGraph workflow with Human-In-The-Loop support."""
    builder = StateGraph(ARBState)

    # Register nodes
    builder.add_node("ingest_memory", ingest_and_retrieve_memory_node)
    builder.add_node("lead_architect", run_lead_architect_node)
    builder.add_node("secops", run_secops_node)
    builder.add_node("finops", run_finops_node)
    builder.add_node("synthesis_validator", run_synthesis_validator_node)
    builder.add_node("finalize_approved", finalize_approved_node)
    builder.add_node("finalize_rejected", finalize_rejected_node)

    # Set flow
    builder.set_entry_point("ingest_memory")
    
    # Fan-out to specialized agents
    builder.add_edge("ingest_memory", "lead_architect")
    builder.add_edge("ingest_memory", "secops")
    builder.add_edge("ingest_memory", "finops")

    # Fan-in to synthesis validator
    builder.add_edge("lead_architect", "synthesis_validator")
    builder.add_edge("secops", "synthesis_validator")
    builder.add_edge("finops", "synthesis_validator")

    # Router from synthesis validator
    builder.add_conditional_edges(
        "synthesis_validator",
        route_validation,
        {
            "wait_for_human": END,
            "revision_loop": "ingest_memory", # Cyclical revision loop
            "finalize_approved": "finalize_approved",
            "finalize_rejected": "finalize_rejected"
        }
    )

    builder.add_edge("finalize_approved", END)
    builder.add_edge("finalize_rejected", END)

    return builder.compile()

# Global compiled graph instance
arb_graph = build_arb_graph()
