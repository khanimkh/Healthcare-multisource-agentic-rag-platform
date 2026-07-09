from typing import Any, Dict, List, Optional

from app.backend.prompts.final_answer_prompt import (
    FINAL_ANSWER_SYSTEM_PROMPT,
    build_final_answer_prompt
)
from app.backend.services.llm_service import LLMService
from app.backend.utils.logger import get_logger


logger = get_logger(__name__)


class FinalAnswerAgent:
    def __init__(self):
        self.llm_service = LLMService()

    def compose(
        self,
        question: str,
        route: str,
        tool_answer: str,
        sources: Optional[List[Dict[str, Any]]] = None,
        sql: Optional[str] = None
    ) -> Dict[str, Any]:
        prompt = build_final_answer_prompt(
            question=question,
            route=route,
            tool_answer=tool_answer,
            sources=sources,
            sql=sql
        )

        final_answer = self.llm_service.generate(
            prompt=prompt,
            system_prompt=FINAL_ANSWER_SYSTEM_PROMPT,
            max_tokens=800,
            temperature=0.3
        )

        logger.info(f"Composed final answer for route={route!r}.")

        return {
            "answer": final_answer,
            "route": route,
            "sources": sources or [],
            "sql": sql
        }
