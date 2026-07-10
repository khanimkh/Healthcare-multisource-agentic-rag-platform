from typing import Any, Dict, List, Optional

import pandas as pd

from app.backend.prompts.classification_prompt import (
    CLASSIFICATION_SYSTEM_PROMPT,
    build_document_classification_prompt,
    build_structured_classification_prompt
)
from app.backend.services.aws_storage_service import OpenSearchVectorStore
from app.backend.services.llm_service import LLMService
from app.backend.tools.document_resolution import resolve_document
from app.backend.utils.logger import get_logger


logger = get_logger(__name__)


class ClassificationAgent:
    def __init__(self):
        self.llm_service = LLMService()
        self.vector_store = OpenSearchVectorStore()

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

    def classify_uploaded_document(
        self,
        question: str,
        available_documents: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        document = resolve_document(question, available_documents or [])

        if document is None:
            logger.info("No document resolved for classification, falling back to question text.")
            return {
                "category": self.classify_document(question),
                "document": None
            }

        text = self.vector_store.get_document_text(document["file_id"])

        if not text.strip():
            logger.warning(f"Resolved document {document['file_name']!r} has no indexed text.")
            return {
                "category": self.classify_document(question),
                "document": None
            }

        return {
            "category": self.classify_document(text),
            "document": document
        }
