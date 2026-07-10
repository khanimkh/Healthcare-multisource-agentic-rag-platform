import json
import re
from typing import Any, Dict, List, Optional

from app.backend.prompts.rag_prompt import RAG_SYSTEM_PROMPT, build_rag_prompt
from app.backend.prompts.rerank_prompt import RERANK_SYSTEM_PROMPT, build_rerank_prompt
from app.backend.services.aws_storage_service import OpenSearchVectorStore
from app.backend.services.embedding_service import EmbeddingService
from app.backend.services.llm_service import LLMService
from app.backend.utils.logger import get_logger


logger = get_logger(__name__)


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

        chunks = self.vector_store.search_chunks(
            embedding=embedding,
            k=k,
            document_type=document_type
        )

        logger.info(f"Retrieved {len(chunks)} chunk(s) for k={k}.")

        return self.rerank_chunks(question, chunks)

    def rerank_chunks(
        self,
        question: str,
        chunks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        if len(chunks) <= 1:
            return chunks

        prompt = build_rerank_prompt(question=question, chunks=chunks)

        response = self.llm_service.generate(
            prompt=prompt,
            system_prompt=RERANK_SYSTEM_PROMPT,
            max_tokens=100,
            temperature=0
        )

        order = self._parse_rerank_order(response, len(chunks))

        if order is None:
            logger.warning("Rerank response could not be parsed, keeping original order.")
            return chunks

        reranked = [chunks[i] for i in order]
        seen = set(order)
        reranked.extend(chunk for i, chunk in enumerate(chunks) if i not in seen)

        return reranked

    def _parse_rerank_order(self, response: str, chunk_count: int) -> Optional[List[int]]:
        match = re.search(r"\[[\d,\s]*\]", response)

        if not match:
            return None

        try:
            order = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None

        if not isinstance(order, list):
            return None

        return [i for i in order if isinstance(i, int) and 0 <= i < chunk_count]

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
            "sources": self._deduplicate_sources(chunks)
        }

    def _deduplicate_sources(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen = set()
        sources = []

        for chunk in chunks:
            key = chunk.get("file_id") or chunk.get("file_name")

            if key in seen:
                continue

            seen.add(key)
            sources.append({
                "file_name": chunk.get("file_name"),
                "file_id": chunk.get("file_id"),
                "s3_uri": chunk.get("s3_uri"),
                "score": chunk.get("score")
            })

        return sources
