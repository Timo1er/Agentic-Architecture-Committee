from typing import Dict, Any, List, Optional, TypedDict, Annotated
import operator

class ARBState(TypedDict):
    review_id: str
    title: str
    target_clouds: List[str] # AWS, GCP, Azure, AliCloud, OVH
    llm_provider: str # google, anthropic, openai, mistral, aws
    model_name: Optional[str]
    raw_inputs: Dict[str, Any] # diagram_parsed, terraform_parsed, services_parsed
    global_guidelines: Optional[str]
    agent_sources: Optional[Dict[str, List[Dict[str, Any]]]]
    memory_context: Optional[str]
    
    # Agent outputs
    lead_architect_output: Optional[Dict[str, Any]]
    secops_output: Optional[Dict[str, Any]]
    finops_output: Optional[Dict[str, Any]]
    adr_output: Optional[Dict[str, Any]]
    
    # Incremental ADR Identification
    adr_number: Optional[int]
    adr_prefix: Optional[str]
    
    # Human-In-The-Loop (HITL) & Revision Tracking
    human_feedback: Optional[Dict[str, Any]] # {rating: 4, verdict: "revision_requested", comments: "...", corrections: "..."}
    status: str # "analyzing", "awaiting_human_validation", "approved", "revision_requested", "rejected"
    iteration_count: int
    logs: Annotated[List[str], operator.add]
