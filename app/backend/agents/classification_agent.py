import pandas as pd

from app.backend.prompts.classification_prompt import (
    CLASSIFICATION_SYSTEM_PROMPT,
    build_document_classification_prompt,
    build_structured_classification_prompt
)
from app.backend.services.llm_service import LLMService
from app.backend.utils.logger import get_logger


logger = get_logger(__name__)


class ClassificationAgent:
    def __init__(self):
        self.llm_service = LLMService()

    def classify_document(self, text: str) -> str:
        prompt = build_document_classification_prompt(text)

        category = self.llm_service.generate(
            prompt=prompt,
            system_prompt=CLASSIFICATION_SYSTEM_PROMPT,
            max_tokens=50,
            temperature=0
        )

        category = category.strip().lower()
        logger.info(f"Classified document as {category!r}.")
        return category

    def classify_structured_data(self, df: pd.DataFrame) -> str:
        prompt = build_structured_classification_prompt(df.columns.tolist())

        category = self.llm_service.generate(
            prompt=prompt,
            system_prompt=CLASSIFICATION_SYSTEM_PROMPT,
            max_tokens=50,
            temperature=0
        )

        category = category.strip().lower()
        logger.info(f"Classified structured dataset as {category!r}.")
        return category
