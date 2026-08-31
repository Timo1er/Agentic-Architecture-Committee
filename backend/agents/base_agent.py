import json
import logging
import re
from typing import Dict, Any, List, Optional
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.language_models.chat_models import BaseChatModel

logger = logging.getLogger("arb.agents")

class BaseAgent:
    """Base class for all ARB specialized agents."""

    def __init__(self, role_name: str, system_prompt: str, llm: BaseChatModel):
        self.role_name = role_name
        self.system_prompt = system_prompt
        self.llm = llm

    def _extract_json(self, response_text: str) -> Dict[str, Any]:
        """Extract and parse JSON object from markdown or raw LLM output."""
        try:
            # Check for ```json ... ``` blocks
            json_block = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response_text)
            if json_block:
                return json.loads(json_block.group(1).strip())
            
            # Fallback to direct json search
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}')
            if start_idx != -1 and end_idx != -1:
                return json.loads(response_text[start_idx:end_idx + 1])
            
            return json.loads(response_text)
        except Exception as e:
            logger.warning(f"Failed to parse strict JSON from {self.role_name}: {e}. Returning structured text wrapper.")
            return {
                "role": self.role_name,
                "raw_analysis": response_text,
                "status": "completed_with_raw_text"
            }

    async def execute_analysis(self, context_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Execute agent evaluation on the target architecture payload."""
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=json.dumps(context_payload, indent=2))
        ]

        try:
            # LangChain chat invocation
            if hasattr(self.llm, "ainvoke"):
                response = await self.llm.ainvoke(messages)
            else:
                response = self.llm.invoke(messages)
            
            content = response.content if hasattr(response, "content") else str(response)
            return self._extract_json(content)
        except Exception as e:
            logger.error(f"Error executing {self.role_name}: {e}")
            return {
                "role": self.role_name,
                "error": str(e),
                "status": "failed"
            }
