from typing import Any, Dict, List, Optional

from app.backend.services.model_service import ModelService


class LLMService:
    def __init__(self):
        self.model_service = ModelService()

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.3
    ) -> str:
        return self.model_service.invoke_text_model(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature
        )

    def generate_with_history(
        self,
        question: str,
        history: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.3
    ) -> str:
        conversation = "\n".join(
            f"{turn['role']}: {turn['content']}" for turn in history
        )

        prompt = f"""
        Conversation so far:
        {conversation}

        New question:
        {question}
        """

        return self.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature
        )
