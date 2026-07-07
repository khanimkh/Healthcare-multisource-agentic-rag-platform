from typing import Any, Dict, List, Optional

from app.backend.prompts.rag_prompt import RAG_SYSTEM_PROMPT, build_rag_prompt
from app.backend.services.aws_storage_service import OpenSearchVectorStore
from app.backend.services.embedding_service import EmbeddingService
from app.backend.services.llm_service import LLMService


class RAGAgent:
    def __init__(self):
        self.embedding_service = EmbeddingService()
        self.vector_store = OpenSearchVectorStore()
        self.llm_service = LLMService()

    def retrieve(
        self,
        question: str,
        k: int = 5,
        document_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        embedding = self.embedding_service.create_embedding(question)

        return self.vector_store.search_chunks(
            embedding=embedding,
            k=k,
            document_type=document_type
        )

    def answer(
        self,
        question: str,
        k: int = 5,
        document_type: Optional[str] = None
    ) -> Dict[str, Any]:
        chunks = self.retrieve(question=question, k=k, document_type=document_type)

        prompt = build_rag_prompt(question=question, chunks=chunks)

        answer = self.llm_service.generate(
            prompt=prompt,
            system_prompt=RAG_SYSTEM_PROMPT,
            max_tokens=800,
            temperature=0.2
        )

        return {
            "answer": answer,
            "sources": [
                {
                    "file_name": chunk.get("file_name"),
                    "file_id": chunk.get("file_id"),
                    "s3_uri": chunk.get("s3_uri"),
                    "score": chunk.get("score")
                }
                for chunk in chunks
            ]
        }
