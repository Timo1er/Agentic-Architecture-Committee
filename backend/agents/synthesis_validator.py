from typing import Dict, Any, List
import json
from langchain_core.language_models.chat_models import BaseChatModel
from backend.agents.base_agent import BaseAgent

SYNTHESIS_SYSTEM_PROMPT = """You are the **Validator / Synthesis Agent** and Chairperson of the Architecture Review Board (ARB).
Your role is to synthesize the analytical findings from the Lead Architect, SecOps & Compliance, and FinOps agents into an industry-standard **Architecture Decision Record (ADR)**, risk matrix, and alternatives evaluation across AWS, GCP, Azure, AliCloud, and OVH.

If human reviewer feedback or requested revisions are present in the context, you MUST incorporate the operator's corrections into this revised ADR.

### Standard ADR Structure Required:
1. **Title & Metadata**: ADR Number, Title, Status (PROPOSED / ACCEPTED / REVISION_REQUIRED).
2. **Context**: Technical context, business drivers, requirements, and constraints.
3. **Decision**: Concrete architectural decision and selected patterns.
4. **Consequences**: Positive and negative trade-offs.
5. **Critical Risk Matrix**: List of architectural, security, and operational risks with severity (HIGH/MED/LOW), impact, and mitigation.
6. **FinOps & Capacity Summary**: Monthly cost estimate and resource sizing.
7. **Considered Alternatives & Rejection Rationale**: 2+ rejected architectural alternatives with reasons.

You MUST respond strictly in valid JSON with the following structure:
```json
{
  "role": "Validator & Synthesis",
  "adr_number": 1,
  "adr_title": "ADR-001: Short Title",
  "status": "PROPOSED",
  "context": "Comprehensive context description",
  "decision": "Concrete architectural decisions adopted",
  "consequences": {
    "positive": ["Positive outcome 1", "Positive outcome 2"],
    "negative": ["Trade-off / cost 1", "Trade-off / cost 2"]
  },
  "risk_matrix": [
    {"risk": "Risk description", "severity": "HIGH | MEDIUM | LOW", "impact": "Impact description", "mitigation": "Concrete mitigation"}
  ],
  "cost_breakdown": {
    "estimated_monthly_usd": 1500.0,
    "summary": "Summary of primary cost drivers"
  },
  "alternatives_considered": [
    {"alternative": "Alternative approach 1", "reason_rejected": "Why it was not chosen"}
  ],
  "full_markdown_adr": "# Full generated markdown ADR text..."
}
```
"""

class SynthesisValidatorAgent(BaseAgent):
    def __init__(self, llm: BaseChatModel):
        super().__init__(
            role_name="Synthesis & Validator",
            system_prompt=SYNTHESIS_SYSTEM_PROMPT,
            llm=llm
        )

    def generate_markdown(self, adr_data: Dict[str, Any], raw_analyses: Dict[str, Any]) -> str:
        """Helper to format a complete, polished Markdown document if full_markdown_adr was omitted or partial."""
        if adr_data.get("full_markdown_adr") and len(adr_data["full_markdown_adr"]) > 100:
            return adr_data["full_markdown_adr"]

        title = adr_data.get("adr_title", "Architecture Decision Record")
        status = adr_data.get("status", "PROPOSED")
        context = adr_data.get("context", "Context provided in review input.")
        decision = adr_data.get("decision", "Architecture evaluated and accepted with specified patterns.")
        
        pos_list = "\n".join([f"- {p}" for p in adr_data.get("consequences", {}).get("positive", [])]) or "- High scalability and reliability"
        neg_list = "\n".join([f"- {n}" for n in adr_data.get("consequences", {}).get("negative", [])]) or "- Operational overhead for distributed telemetry"

        risks = adr_data.get("risk_matrix", [])
        risk_table_rows = []
        for r in risks:
            risk_table_rows.append(f"| {r.get('risk')} | `{r.get('severity')}` | {r.get('impact')} | {r.get('mitigation')} |")
        risk_table = "\n".join(risk_table_rows) if risk_table_rows else "| None identified | `LOW` | Minimal | Standard observability |"

        alts = adr_data.get("alternatives_considered", [])
        alts_list = "\n".join([f"- **{a.get('alternative')}**: {a.get('reason_rejected')}" for a in alts]) or "- Monolith: Insufficient multi-region scaling"

        md = f"""# {title}

**Status:** `{status}`  
**Date:** Evaluated by Architecture Review Board  
**Target Clouds:** AWS, GCP, Azure, AliCloud, OVH  

---

## 1. Context & Business Drivers
{context}

---

## 2. Architectural Decision
{decision}

---

## 3. Consequences & Trade-offs
### Positive Outcomes
{pos_list}

### Negative Trade-offs
{neg_list}

---

## 4. Critical Risk Matrix
| Risk Description | Severity | Impact | Mitigation Strategy |
| :--- | :--- | :--- | :--- |
{risk_table}

---

## 5. FinOps & Cost Projection
- **Estimated Monthly Cost:** \${adr_data.get('cost_breakdown', {}).get('estimated_monthly_usd', 1500.0):,.2f} USD
- **Key Cost Drivers:** {adr_data.get('cost_breakdown', {}).get('summary', 'Compute instances, managed datastores, and egress routing.')}

---

## 6. Considered Alternatives & Rejection Rationale
{alts_list}
"""
        return md
