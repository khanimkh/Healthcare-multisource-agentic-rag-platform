from typing import Any, Dict, Optional

from app.backend.graphs.question_graph import question_graph
from app.backend.services.athena_service import AthenaService
from app.backend.services.document_store_service import DocumentStore
from app.backend.services.memory_service import MemoryService
from app.backend.services.schema_service import SchemaService
from app.backend.utils.logger import get_logger


logger = get_logger(__name__)


class QuestionWorkflow:
    def __init__(self):
        self.schema_service = SchemaService()
        self.document_store = DocumentStore()
        self.memory_service = MemoryService()
        self.athena_service = AthenaService()

    def _format_conversation_context(self, session_id: Optional[str]) -> str:
        if not session_id:
            return ""

        history = self.memory_service.get_recent_messages(session_id)

        return "\n".join(f"{turn['role']}: {turn['content']}" for turn in history)

    def ask(self, question: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        logger.info(f"Received question (session_id={session_id!r}): {question!r}")

        schema = self.schema_service.describe_tables()
        athena_tables = self.athena_service.list_tables()
        document_records = self.document_store.list_indexed_document_records()

        initial_state: Dict[str, Any] = {
            "question": question,
            "available_tables": list(schema.keys()) + athena_tables,
            "available_documents": [record["file_name"] for record in document_records],
            "available_document_records": document_records,
            "schema_description": self.schema_service.format_description(schema),
            "conversation_context": self._format_conversation_context(session_id)
        }

        if session_id:
            initial_state["session_id"] = session_id

        final_state = question_graph.invoke(initial_state)

        logger.info(f"Answered via route={final_state.get('route')!r} (session_id={session_id!r}).")

        return {
            "answer": final_state.get("final_answer"),
            "route": final_state.get("route"),
            "sql": final_state.get("sql"),
            "sources": final_state.get("sources", [])
        }
