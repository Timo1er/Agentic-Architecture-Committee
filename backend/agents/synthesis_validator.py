import re
from typing import Dict, Any, List
import json
from langchain_core.language_models.chat_models import BaseChatModel
from backend.agents.base_agent import BaseAgent, sanitize_risk_matrix

SYNTHESIS_SYSTEM_PROMPT = """You are the **Validator / Synthesis Agent** and Chairperson of the Architecture Review Board (ARB).
Your role is to synthesize the analytical findings from the Lead Architect, SecOps & Compliance, and FinOps agents into an industry-standard **Architecture Decision Record (ADR)**, risk matrix, and alternatives evaluation across AWS, GCP, Azure, AliCloud, and OVH.

If human reviewer feedback or requested revisions are present in the context, you MUST incorporate the operator's corrections into this revised ADR.

### Standard ADR Structure Required:
1. **Title & Metadata**: Check context for `assigned_adr_number` (e.g., 2, 3) and `assigned_adr_prefix` (e.g., "ADR-002", "ADR-003"). You MUST use the assigned number and prefix! Keep the title concise, punchy, and strictly under 50 characters (e.g., "ADR-002: AWS HA Event Processing").
2. **Context**: 2-3 focused, readable paragraphs detailing technical context, business drivers, requirements, and constraints. Must be clean human-readable prose. Do NOT include raw JSON syntax.
3. **Decision**: Concrete architectural decision and selected patterns. Concise and definitive.
4. **Consequences**: Positive and negative trade-offs (3-5 items each).
5. **Critical Risk Matrix**: 3-5 high-priority architectural, security, and operational risks. Keep each risk description concise (under 25 words), impact clear (under 25 words), and mitigation actionable (under 30 words).
6. **FinOps & Capacity Summary**: Monthly cost estimate and resource sizing summary.
7. **Considered Alternatives & Rejection Rationale**: 2+ rejected architectural alternatives with reasons.

You MUST respond strictly in valid JSON with the following structure:
```json
{
  "role": "Validator & Synthesis",
  "adr_number": 2,
  "adr_title": "ADR-002: Concise Title (<50 chars)",
  "status": "PROPOSED",
  "context": "Clear, concise technical context and business drivers...",
  "decision": "Concrete architectural decisions adopted...",
  "consequences": {
    "positive": ["Positive outcome 1", "Positive outcome 2"],
    "negative": ["Trade-off / cost 1", "Trade-off / cost 2"]
  },
  "risk_matrix": [
    {"risk": "Concise risk description", "severity": "HIGH", "impact": "Direct impact description", "mitigation": "Concrete actionable mitigation"}
  ],
  "cost_breakdown": {
    "estimated_monthly_usd": 1500.0,
    "summary": "Summary of primary cost drivers"
  },
  "alternatives_considered": [
    {"alternative": "Alternative approach 1", "reason_rejected": "Why it was not chosen"}
  ],
  "full_markdown_adr": "# ADR-002: Concise Title\\n\\n## 1. Title & Metadata\\n- **ADR Number:** 2..."
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
        """Helper to format a complete, polished Markdown document ensuring correct numbering and clean formatting."""
        assigned_num = raw_analyses.get("assigned_adr_number") or adr_data.get("adr_number") or 1
        assigned_pfx = raw_analyses.get("assigned_adr_prefix") or adr_data.get("adr_prefix") or f"ADR-{assigned_num:03d}"

        existing_md = adr_data.get("full_markdown_adr")
        if existing_md and len(existing_md) > 100:
            # Check if it has corrupted JSON residue; if so, regenerate clean markdown
            if not any(bad in existing_md for bad in ['"risk_matrix":', 'risk_matrix":', '"decision":', 'full_markdown_adr":']):
                # Enforce correct prefix in the markdown header
                updated_md = re.sub(r'^#\s*ADR-\d+\s*:\s*', f'# {assigned_pfx}: ', existing_md.strip())
                updated_md = re.sub(r'-\s*\*\*ADR Number:\*\*\s*\d+', f'- **ADR Number:** {assigned_num}', updated_md)
                return updated_md

        raw_title = adr_data.get("adr_title") or f"{assigned_pfx}: Architecture Decision Record"
        clean_subj = re.sub(r'^ADR-\d+\s*:\s*', '', raw_title.replace('#', '').strip())
        title = f"{assigned_pfx}: {clean_subj}"

        status = adr_data.get("status", "PROPOSED")
        context = adr_data.get("context", "Context provided in review input.")
        decision = adr_data.get("decision", "Architecture evaluated and accepted with specified patterns.")
        
        pos_list = "\n".join([f"- {p}" for p in adr_data.get("consequences", {}).get("positive", [])]) or "- High scalability and reliability"
        neg_list = "\n".join([f"- {n}" for n in adr_data.get("consequences", {}).get("negative", [])]) or "- Operational overhead for distributed telemetry"

        risks = sanitize_risk_matrix(adr_data.get("risk_matrix", []))
        risk_table_rows = []
        for r in risks:
            # Replace pipe characters with slashes to preserve markdown table integrity
            r_desc = str(r.get('risk', '')).replace('|', '/')
            r_imp = str(r.get('impact', '')).replace('|', '/')
            r_mit = str(r.get('mitigation', '')).replace('|', '/')
            risk_table_rows.append(f"| {r_desc} | `{r.get('severity', 'MEDIUM')}` | {r_imp} | {r_mit} |")
        risk_table = "\n".join(risk_table_rows) if risk_table_rows else "| None identified | `LOW` | Minimal | Standard observability |"

        alts = adr_data.get("alternatives_considered", [])
        alts_list = "\n".join([f"- **{a.get('alternative')}**: {a.get('reason_rejected')}" for a in alts]) or "- Monolith: Insufficient multi-region scaling"

        md = f"""# {title}

**ADR Number:** {assigned_num}  
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
- **Estimated Monthly Cost:** ${adr_data.get('cost_breakdown', {}).get('estimated_monthly_usd', 1500.0):,.2f} USD
- **Key Cost Drivers:** {adr_data.get('cost_breakdown', {}).get('summary', 'Compute instances, managed datastores, and egress routing.')}

---

## 6. Considered Alternatives & Rejection Rationale
{alts_list}
"""
        return md
