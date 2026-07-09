from pathlib import Path
from typing import Any, Dict, List, Optional

from app.backend.prompts.summary_prompt import SUMMARY_SYSTEM_PROMPT, build_summary_prompt
from app.backend.services.aws_storage_service import OpenSearchVectorStore
from app.backend.services.llm_service import LLMService
from app.backend.tools.rag_utils import chunk_documents
from app.backend.utils.logger import get_logger


logger = get_logger(__name__)


class SummarizationAgent:
    MAP_REDUCE_THRESHOLD = 6000

    def __init__(self):
        self.llm_service = LLMService()
        self.vector_store = OpenSearchVectorStore()

    def summarize(self, text: str, instructions: Optional[str] = None) -> str:
        if len(text) <= self.MAP_REDUCE_THRESHOLD:
            return self._summarize_piece(text, instructions)

        logger.info(f"Text length {len(text)} exceeds threshold, using map-reduce summarization.")

        pieces = chunk_documents(text, chunk_size=self.MAP_REDUCE_THRESHOLD, chunk_overlap=200)
        partial_summaries = [self._summarize_piece(piece, instructions) for piece in pieces]
        combined = "\n\n".join(partial_summaries)

        reduce_instructions = (
            f"{instructions}\n\nCombine these partial summaries into one clear, non-repetitive summary."
            if instructions
            else "Combine these partial summaries into one clear, non-repetitive summary."
        )

        return self._summarize_piece(combined, reduce_instructions)

    def summarize_document(
        self,
        question: str,
        available_documents: Optional[List[Dict[str, str]]] = None,
        instructions: Optional[str] = None
    ) -> Dict[str, Any]:
        document = self._resolve_document(question, available_documents or [])

        if document is None:
            logger.info("No document resolved for summarization, falling back to question text.")
            return {
                "summary": self.summarize(question, instructions),
                "document": None
            }

        text = self.vector_store.get_document_text(document["file_id"])

        if not text.strip():
            logger.warning(f"Resolved document {document['file_name']!r} has no indexed text.")
            return {
                "summary": self.summarize(question, instructions),
                "document": None
            }

        logger.info(f"Summarizing resolved document {document['file_name']!r} ({len(text)} chars).")
        return {
            "summary": self.summarize(text, instructions or question),
            "document": document
        }

    def _resolve_document(
        self,
        question: str,
        available_documents: List[Dict[str, str]]
    ) -> Optional[Dict[str, str]]:
        question_lower = question.lower()
        best_document = None
        best_score = 0.0

        for document in available_documents:
            stem = Path(document["file_name"]).stem.lower().replace("_", " ").replace("-", " ")
            words = [word for word in stem.split() if len(word) > 2]

            if not words:
                continue

            score = sum(1 for word in words if word in question_lower) / len(words)

            if score > best_score:
                best_score = score
                best_document = document

        return best_document if best_score >= 0.5 else None

    def _summarize_piece(self, text: str, instructions: Optional[str]) -> str:
        prompt = build_summary_prompt(text=text, instructions=instructions)

        return self.llm_service.generate(
            prompt=prompt,
            system_prompt=SUMMARY_SYSTEM_PROMPT,
            max_tokens=600,
            temperature=0.3
        )
