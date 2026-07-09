from typing import List, Optional

from app.backend.prompts.router_prompt import (
    ROUTES,
    ROUTER_SYSTEM_PROMPT,
    build_router_prompt
)
from app.backend.services.llm_service import LLMService
from app.backend.utils.logger import get_logger


logger = get_logger(__name__)


class RouterAgent:
    def __init__(self):
        self.llm_service = LLMService()

    def route(
        self,
        question: str,
        available_tables: Optional[List[str]] = None,
        available_documents: Optional[List[str]] = None,
        conversation_context: Optional[str] = None
    ) -> str:
        prompt = build_router_prompt(
            question=question,
            available_tables=available_tables,
            available_documents=available_documents,
            conversation_context=conversation_context
        )

        response = self.llm_service.generate(
            prompt=prompt,
            system_prompt=ROUTER_SYSTEM_PROMPT,
            max_tokens=20,
            temperature=0
        )

        route = response.strip().lower()

        if route not in ROUTES:
            logger.warning(f"Router returned invalid route {route!r}, falling back to 'rag'.")
            return "rag"

        logger.info(f"Routed question to {route!r}.")
        return route
