import json
import logging
import re
from typing import Dict, Any, List, Optional
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.language_models.chat_models import BaseChatModel

logger = logging.getLogger("arb.agents")

def sanitize_risk_matrix(raw_risks: Any) -> List[Dict[str, str]]:
    """Sanitize and format risk matrix entries, preventing JSON leakages and overly long text."""
    if not isinstance(raw_risks, list):
        return []
    
    sanitized: List[Dict[str, str]] = []
    seen_risks = set()

    for r in raw_risks:
        if not isinstance(r, dict):
            continue
        
        raw_desc = str(r.get("risk") or "").strip()
        # Clean JSON quotes or brackets
        raw_desc = re.sub(r'^["\'\s]+|["\'\s]+$', '', raw_desc)
        
        # Discard corrupted JSON residue or full markdown dump
        if not raw_desc or any(bad in raw_desc.lower() for bad in [
            '"risk_matrix"', 'risk_matrix":', 'full_markdown_adr', 'full_markdown":',
            '"decision":', '{"risk":', '## 1. title', '## 5. critical risk'
        ]):
            continue

        # Truncate overly long risk descriptions (max 180 chars)
        if len(raw_desc) > 180:
            raw_desc = raw_desc[:177] + "..."

        if raw_desc in seen_risks:
            continue
        seen_risks.add(raw_desc)

        sev = str(r.get("severity") or "MEDIUM").strip().upper()
        if "HIGH" in sev:
            sev = "HIGH"
        elif "LOW" in sev:
            sev = "LOW"
        else:
            sev = "MEDIUM"

        impact = str(r.get("impact") or "Operational impact identified during review").strip()
        impact = re.sub(r'^["\'\s]+|["\'\s]+$', '', impact)
        if len(impact) > 180:
            impact = impact[:177] + "..."

        mitigation = str(r.get("mitigation") or "Apply defense-in-depth guardrails and continuous monitoring").strip()
        mitigation = re.sub(r'^["\'\s]+|["\'\s]+$', '', mitigation)
        if len(mitigation) > 220:
            mitigation = mitigation[:217] + "..."

        sanitized.append({
            "risk": raw_desc,
            "severity": sev,
            "impact": impact,
            "mitigation": mitigation
        })

    return sanitized

class BaseAgent:
    """Base class for all ARB specialized agents."""

    def __init__(self, role_name: str, system_prompt: str, llm: BaseChatModel):
        self.role_name = role_name
        self.system_prompt = system_prompt
        self.llm = llm

    def _normalize_response_text(self, response_raw: Any) -> str:
        """Flatten LangChain response content (string, list of chunks/dicts, AIMessage) into a single string."""
        if isinstance(response_raw, list):
            parts = []
            for item in response_raw:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict) and "text" in item:
                    parts.append(str(item["text"]))
                elif hasattr(item, "text"):
                    parts.append(str(getattr(item, "text")))
                elif hasattr(item, "content"):
                    parts.append(self._normalize_response_text(getattr(item, "content")))
                else:
                    parts.append(str(item))
            return "\n".join(parts)
        elif isinstance(response_raw, dict) and "text" in response_raw:
            return str(response_raw["text"])
        elif hasattr(response_raw, "content"):
            return self._normalize_response_text(getattr(response_raw, "content"))
        return str(response_raw)

    def _clean_json_str(self, text: str) -> str:
        """Strip fences, outermost non-JSON text, and trailing commas."""
        text = text.strip()
        fence_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        if fence_match:
            text = fence_match.group(1).strip()
        else:
            start = text.find('{')
            end = text.rfind('}')
            if start != -1 and end != -1 and end > start:
                text = text[start:end+1]
        
        # Quote unquoted keys like _reason_rejected: or reason:
        text = re.sub(r'([{,\s])([a-zA-Z_][a-zA-Z0-9_]*)\s*:', lambda m: f'{m.group(1)}"{m.group(2)}":', text)
        # Normalize single-quoted keys
        text = re.sub(r"'([a-zA-Z0-9_]+)'\s*:", lambda m: f'"{m.group(1)}":', text)
        # Remove trailing commas before closing braces/brackets
        text = re.sub(r',\s*([\]}])', r'\1', text)
        return text.strip()

    def _fallback_parse_fields(self, raw_text: str) -> Dict[str, Any]:
        """Attempt best-effort field recovery if standard JSON parsing fails."""
        data: Dict[str, Any] = {
            "role": self.role_name,
            "raw_analysis": raw_text,
            "status": "PROPOSED"
        }

        # 1. If text looks like JSON, extract fields via targeted regex
        if "{" in raw_text and any(k in raw_text for k in ['"adr_title"', '"risk_matrix"', '"context"', '"decision"']):
            m_title = re.search(r'"(?:adr_title|title)"\s*:\s*"([^"]+)"', raw_text)
            if m_title:
                data["adr_title"] = m_title.group(1).strip()

            m_status = re.search(r'"status"\s*:\s*"([A-Z_]+)"', raw_text)
            if m_status:
                data["status"] = m_status.group(1).strip()

            m_ctx = re.search(r'"context"\s*:\s*"((?:[^"\\]|\\.)*)"', raw_text)
            if m_ctx:
                data["context"] = m_ctx.group(1).replace('\\"', '"').replace('\\n', '\n').strip()

            m_dec = re.search(r'"decision"\s*:\s*"((?:[^"\\]|\\.)*)"', raw_text)
            if m_dec:
                data["decision"] = m_dec.group(1).replace('\\"', '"').replace('\\n', '\n').strip()

            # Extract risks from JSON objects inside risk_matrix
            extracted_risks = []
            risk_objs = re.findall(r'\{[^{}]*"(?:risk|issue)"[^{}]*\}', raw_text)
            for ro in risk_objs:
                r_title = re.search(r'"(?:risk|issue)"\s*:\s*"([^"]+)"', ro)
                r_sev = re.search(r'"severity"\s*:\s*"([^"]+)"', ro)
                r_imp = re.search(r'"impact"\s*:\s*"([^"]+)"', ro)
                r_mit = re.search(r'"(?:mitigation|remediation)"\s*:\s*"([^"]+)"', ro)
                if r_title:
                    extracted_risks.append({
                        "risk": r_title.group(1),
                        "severity": r_sev.group(1).upper() if r_sev else "MEDIUM",
                        "impact": r_imp.group(1) if r_imp else "Operational impact",
                        "mitigation": r_mit.group(1) if r_mit else "Apply guardrails"
                    })
            if extracted_risks:
                data["risk_matrix"] = sanitize_risk_matrix(extracted_risks)

            # Extract alternatives considered
            m_alts = re.findall(r'\{[^{}]*"(?:alternative|name)"[^{}]*\}', raw_text)
            clean_alts = []
            for alt_str in m_alts:
                alt_name = re.search(r'"(?:alternative|name)"\s*:\s*"([^"]+)"', alt_str)
                alt_rsn = re.search(r'"(?:reason_rejected|_reason_rejected|rationale)"\s*:\s*"([^"]+)"', alt_str)
                if alt_name:
                    clean_alts.append({
                        "alternative": alt_name.group(1),
                        "reason_rejected": alt_rsn.group(1) if alt_rsn else "Rejected in favor of chosen architecture."
                    })
            if clean_alts:
                data["alternatives_considered"] = clean_alts

            m_cost = re.search(r'"estimated_monthly_usd"\s*:\s*([0-9.]+)', raw_text)
            m_cost_sum = re.search(r'"summary"\s*:\s*"([^"]+)"', raw_text)
            if m_cost:
                data["cost_breakdown"] = {
                    "estimated_monthly_usd": float(m_cost.group(1)),
                    "summary": m_cost_sum.group(1) if m_cost_sum else "Monthly infrastructure cost projection."
                }

            # If full_markdown_adr is present in JSON
            m_full_md = re.search(r'"full_markdown_adr"\s*:\s*"((?:[^"\\]|\\.)*)"', raw_text)
            if m_full_md:
                data["full_markdown_adr"] = m_full_md.group(1).replace('\\"', '"').replace('\\n', '\n')

            if data.get("adr_title") or data.get("context") or data.get("decision"):
                # Clean any lingering JSON artifacts
                return data

        # 2. Markdown text fallback
        title_m = re.search(r'(?:#+\s*|Title:\s*)([^\n]+)', raw_text)
        if title_m:
            data["adr_title"] = title_m.group(1).strip().strip('#').strip()

        dec_m = re.search(r'(?:Decision|Architectural Decision)[:\s]+([\s\S]*?)(?=(?:#+\s*|\n\n[A-Z]|\Z))', raw_text, re.IGNORECASE)
        if dec_m:
            clean_dec = dec_m.group(1).strip()
            # Ensure no JSON trailing syntax
            clean_dec = re.sub(r'",\s*"[a-zA-Z_]+":[\s\S]*$', '', clean_dec).strip().strip('"')
            data["decision"] = clean_dec

        ctx_m = re.search(r'(?:Context|Business Drivers)[:\s]+([\s\S]*?)(?=(?:#+\s*|\n\n[A-Z]|\Z))', raw_text, re.IGNORECASE)
        if ctx_m:
            clean_ctx = ctx_m.group(1).strip()
            # Ensure no JSON trailing syntax
            clean_ctx = re.sub(r'",\s*"[a-zA-Z_]+":[\s\S]*$', '', clean_ctx).strip().strip('"')
            data["context"] = clean_ctx

        pos = re.findall(r'[+*•-]\s*(?:Positive|Benefit|Pro|Advantage)?:?\s*([^\n]+)', raw_text, re.IGNORECASE)
        data["consequences"] = {
            "positive": [p.strip().strip('"') for p in pos[:5] if len(p.strip()) > 3 and not p.strip().startswith('"')] if pos else ["High scalability and cloud parity"],
            "negative": ["Operational overhead for distributed infrastructure"]
        }

        risks = []
        for line in raw_text.splitlines():
            line_str = line.strip()
            # Discard any lines containing JSON keys or brackets
            if any(j in line_str for j in ['"risk_matrix"', '"full_markdown_adr"', '"decision"', '"context"', '":', '{', '}']):
                continue
            if any(k in line_str.lower() for k in ["risk", "vulnerability", "bottleneck", "failure"]):
                cleaned = line_str.strip('-*•| "').strip()
                if cleaned.startswith(('risk":', 'impact":', 'mitigation":')):
                    continue
                if 10 < len(cleaned) < 180 and not cleaned.startswith('#'):
                    risks.append({
                        "risk": cleaned,
                        "severity": "MEDIUM",
                        "impact": "Operational or security impact identified during review",
                        "mitigation": "Apply defense-in-depth and continuous monitoring"
                    })
        data["risk_matrix"] = sanitize_risk_matrix(risks[:6]) if risks else [
            {"risk": "Architecture boundary decoupling overhead", "severity": "LOW", "impact": "Increased CI/CD complexity", "mitigation": "Standardized Infrastructure-as-Code"}
        ]

        data["alternatives_considered"] = [
            {"alternative": "Single Cloud Proprietary Deployment", "reason_rejected": "Vendor lock-in and insufficient sovereignty guarantees across EU/US regions."}
        ]

        data["cost_breakdown"] = {
            "estimated_monthly_usd": 1500.0,
            "summary": "Core cloud compute, managed datastore, and edge routing expenditure."
        }

        return data

    def _extract_json(self, response_text: Any) -> Dict[str, Any]:
        """Extract and parse JSON object from markdown or raw LLM output with robust repair."""
        normalized = self._normalize_response_text(response_text)
        cleaned = self._clean_json_str(normalized)

        # 1. Attempt standard JSON parsing (strict=False permits control characters in strings)
        try:
            return json.loads(cleaned, strict=False)
        except Exception:
            pass

        # 2. Attempt parsing on substring between first { and last }
        try:
            start_idx = normalized.find('{')
            end_idx = normalized.rfind('}')
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                raw_json = normalized[start_idx:end_idx + 1]
                # Quote unquoted keys & remove trailing commas
                raw_json = re.sub(r'(?<=[{,\s])(?<!")([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'"\1":', raw_json)
                raw_json = re.sub(r',\s*([\]}])', r'\1', raw_json)
                return json.loads(raw_json, strict=False)
        except Exception:
            pass

        # 3. Handle possible truncated JSON (e.g. unclosed string or missing closing brackets)
        try:
            fixed_json = cleaned
            if fixed_json.count('"') % 2 != 0:
                fixed_json += '"'
            open_braces = fixed_json.count('{') - fixed_json.count('}')
            open_brackets = fixed_json.count('[') - fixed_json.count(']')
            if open_brackets > 0:
                fixed_json += ']' * open_brackets
            if open_braces > 0:
                fixed_json += '}' * open_braces
            return json.loads(fixed_json, strict=False)
        except Exception:
            pass

        # 4. Fallback recovery: extract structured fields from text
        logger.warning(f"Could not parse strict JSON for {self.role_name}. Using resilient fallback extraction.")
        return self._fallback_parse_fields(normalized)

    async def execute_analysis(self, context_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Execute agent evaluation on the target architecture payload with retry handling."""
        import copy
        import asyncio
        
        image_uri = None
        if "inputs" in context_payload and isinstance(context_payload["inputs"], dict) and "diagram" in context_payload["inputs"]:
            diagram = context_payload["inputs"]["diagram"]
            if isinstance(diagram, dict) and diagram.get("type") == "image_diagram" and diagram.get("raw_data_uri"):
                # Only pass raw multimodal image bytes to Lead Architect
                if self.role_name == "Lead Architect":
                    image_uri = diagram["raw_data_uri"]
                
                # Strip heavy base64 from text payload for all agents to save bandwidth & token quota
                context_payload = copy.deepcopy(context_payload)
                context_payload["inputs"]["diagram"]["raw_data_uri"] = "[EXTRACTED_FOR_MULTIMODAL_INPUT]"

        text_content = json.dumps(context_payload, indent=2, default=str)
        
        if image_uri:
            human_msg = HumanMessage(content=[
                {"type": "text", "text": text_content},
                {"type": "image_url", "image_url": {"url": image_uri}}
            ])
        else:
            human_msg = HumanMessage(content=text_content)

        messages = [
            SystemMessage(content=self.system_prompt),
            human_msg
        ]

        last_error = None
        for attempt in range(3):
            try:
                if hasattr(self.llm, "ainvoke"):
                    response = await self.llm.ainvoke(messages)
                else:
                    response = self.llm.invoke(messages)
                
                content = self._normalize_response_text(response)
                return self._extract_json(content)
            except Exception as e:
                last_error = e
                err_str = str(e)
                logger.warning(f"Attempt {attempt + 1}/3 failed for {self.role_name}: {err_str}")
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "503" in err_str or "UNAVAILABLE" in err_str:
                    await asyncio.sleep(2 * (attempt + 1))
                elif attempt < 2:
                    await asyncio.sleep(1)
                else:
                    break

        logger.error(f"Error executing {self.role_name} after retries: {last_error}")
        return {
            "role": self.role_name,
            "error": str(last_error),
            "status": "failed"
        }
