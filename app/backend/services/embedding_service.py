from typing import List

from app.backend.services.model_service import ModelService


class EmbeddingService:
    def __init__(self):
        self.model_service = ModelService()

    def create_embedding(self, text: str) -> List[float]:
        return self.model_service.invoke_embedding_model(text)

    def create_embeddings(self, texts: List[str]) -> List[List[float]]:
        return [self.create_embedding(text) for text in texts]
