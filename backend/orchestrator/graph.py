import asyncio
import logging
import re
from typing import Dict, Any, Literal, List
from langgraph.graph import StateGraph, END
from backend.orchestrator.state import ARBState
from backend.core.llm_router import LLMRouter
from backend.agents.base_agent import sanitize_risk_matrix
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

def _get_sources_for_agent(agent_key: str, state: ARBState) -> List[Dict[str, Any]]:
    sources_dict = state.get("agent_sources") or {}
    global_sources = sources_dict.get("global", [])
    specific_sources = sources_dict.get(agent_key, [])
    return global_sources + specific_sources

async def run_lead_architect_node(state: ARBState) -> Dict[str, Any]:
    """Node: Execute Lead Architect evaluation."""
    llm = LLMRouter.get_llm(provider=state.get("llm_provider"), model_name=state.get("model_name"))
    agent = LeadArchitectAgent(llm=llm)

    payload = {
        "architecture_title": state["title"],
        "target_clouds": state["target_clouds"],
        "inputs": state["raw_inputs"],
        "guidelines": state.get("global_guidelines"),
        "reference_sources": _get_sources_for_agent("lead_architect", state),
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
        "reference_sources": _get_sources_for_agent("secops_compliance", state),
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
        "reference_sources": _get_sources_for_agent("finops", state),
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
    """Node: Synthesize findings into structured ADR with dynamic incremental numbering."""
    llm = LLMRouter.get_llm(provider=state.get("llm_provider"), model_name=state.get("model_name"))
    agent = SynthesisValidatorAgent(llm=llm)

    adr_num = state.get("adr_number") or 1
    adr_pfx = state.get("adr_prefix") or f"ADR-{adr_num:03d}"

    payload = {
        "architecture_title": state["title"],
        "target_clouds": state["target_clouds"],
        "inputs": state["raw_inputs"],
        "lead_architect_findings": state.get("lead_architect_output"),
        "secops_findings": state.get("secops_output"),
        "finops_findings": state.get("finops_output"),
        "reference_sources": _get_sources_for_agent("synthesis_validator", state),
        "historical_lessons": state.get("memory_context"),
        "prior_human_feedback": state.get("human_feedback"),
        "iteration": state.get("iteration_count", 1),
        "assigned_adr_number": adr_num,
        "assigned_adr_prefix": adr_pfx
    }

    result = await agent.execute_analysis(payload)
    
    # Enforce assigned ADR number and prefix
    result["adr_number"] = adr_num
    result["adr_prefix"] = adr_pfx

    raw_title = result.get("adr_title") or f"{adr_pfx}: {state['title']}"
    clean_subj = re.sub(r'^ADR-\d+\s*:\s*', '', str(raw_title).replace('#', '').strip())
    result["adr_title"] = f"{adr_pfx}: {clean_subj}"

    # Clean context and decision of any leaked JSON residues
    if result.get("context"):
        ctx = str(result["context"])
        ctx = re.sub(r'",\s*"(?:decision|consequences|risk_matrix)":[\s\S]*$', '', ctx)
        result["context"] = ctx.strip().strip('"').strip("'")

    if result.get("decision"):
        dec = str(result["decision"])
        dec = re.sub(r'",\s*"(?:consequences|risk_matrix)":[\s\S]*$', '', dec)
        result["decision"] = dec.strip().strip('"').strip("'")

    # Sanitize and validate risk_matrix
    if not result.get("risk_matrix") or not isinstance(result.get("risk_matrix"), list):
        result["risk_matrix"] = []
    result["risk_matrix"] = sanitize_risk_matrix(result["risk_matrix"])

    # If risk_matrix is empty, extract from secops_output and lead_architect_output
    if len(result["risk_matrix"]) == 0:
        secops = state.get("secops_output") or {}
        if isinstance(secops, dict):
            for vuln in secops.get("critical_vulnerabilities", []):
                if isinstance(vuln, dict) and vuln.get("issue"):
                    result["risk_matrix"].append({
                        "risk": vuln.get("issue"),
                        "severity": vuln.get("severity", "MEDIUM"),
                        "impact": "Security vulnerability identified by SecOps Agent",
                        "mitigation": vuln.get("remediation", "Apply Zero Trust and network hardening")
                    })
        lead = state.get("lead_architect_output") or {}
        if isinstance(lead, dict):
            for ap in lead.get("anti_patterns_detected", []):
                result["risk_matrix"].append({
                    "risk": f"Anti-Pattern: {ap}",
                    "severity": "MEDIUM",
                    "impact": "Architectural coupling / scalability risk",
                    "mitigation": "Refactor component boundaries and implement circuit breakers"
                })
        result["risk_matrix"] = sanitize_risk_matrix(result["risk_matrix"])

    # Ensure alternatives_considered is present
    if not result.get("alternatives_considered"):
        result["alternatives_considered"] = [
            {"alternative": "Single-Cloud Monolithic Deployment", "reason_rejected": "Lacks cross-cloud portability and fails sovereignty/redundancy requirements."},
            {"alternative": "Unmanaged Self-Hosted Infrastructure", "reason_rejected": "Higher operational maintenance overhead and weaker automated compliance guarantees."}
        ]

    # Ensure decision is present
    if not result.get("decision") or result.get("decision") == "Architecture evaluated and accepted with specified patterns.":
        lead = state.get("lead_architect_output") or {}
        patterns = lead.get("patterns_identified", []) if isinstance(lead, dict) else []
        style = lead.get("architectural_style", "Distributed Cloud-Native Architecture") if isinstance(lead, dict) else "Cloud-Native Architecture"
        if patterns:
            result["decision"] = f"Adopt {style} leveraging {', '.join(patterns)} across target clouds {', '.join(state['target_clouds'])}."
        else:
            result["decision"] = f"Adopt a {style} enforcing zero trust network isolation and resilient multi-cloud service tiering."

    # Ensure clean markdown representation is present with correct prefix
    existing_md = result.get("full_markdown_adr", "")
    if not existing_md or len(existing_md) < 50 or any(bad in existing_md for bad in ['"risk_matrix":', 'risk_matrix":', '"decision":']):
        result["full_markdown_adr"] = agent.generate_markdown(result, payload)
    else:
        # Enforce correct prefix in markdown
        md = re.sub(r'^#\s*ADR-\d+\s*:\s*', f'# {adr_pfx}: ', existing_md.strip())
        md = re.sub(r'-\s*\*\*ADR Number:\*\*\s*\d+', f'- **ADR Number:** {adr_num}', md)
        result["full_markdown_adr"] = md

    return {
        "adr_output": result,
        "status": "awaiting_human_validation",
        "logs": [f"Validator Agent generated {result.get('adr_title', adr_pfx)} and entered Human Validation checkpoint."]
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

    # Sequential pipeline flow (eliminates concurrent API burst rate limiting on Free Tier)
    builder.set_entry_point("ingest_memory")
    builder.add_edge("ingest_memory", "lead_architect")
    builder.add_edge("lead_architect", "secops")
    builder.add_edge("secops", "finops")
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
