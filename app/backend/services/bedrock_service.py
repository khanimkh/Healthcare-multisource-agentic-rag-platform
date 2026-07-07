from typing import List

from app.backend.services.embedding_service import EmbeddingService
from app.backend.services.model_service import ModelService


class BedrockService:
    def __init__(self):
        self.model_service = ModelService()
        self.embedding_service = EmbeddingService()

    def classify_text(self, text: str) -> str:
        prompt = f"""
        Classify the following healthcare content into one category:
        - clinical guideline
        - patient report
        - claims dataset
        - healthcare policy
        - research publication
        - lab result
        - administrative document
        - unknown

       Return only the category name.

       Content:
         {text[:4000]}
        """

        return self.model_service.invoke_text_model(
            prompt=prompt,
            max_tokens=100,
            temperature=0
        )

    def create_embedding(self, text: str) -> List[float]:
        return self.embedding_service.create_embedding(text)
