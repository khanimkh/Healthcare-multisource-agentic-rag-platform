from typing import Any, Dict, List, Optional

from sqlalchemy import create_engine, inspect

from app.backend.config.settings import settings
from app.backend.graphs.question_graph import question_graph
from app.backend.services.athena_service import AthenaService
from app.backend.services.document_store_service import DocumentStore
from app.backend.services.memory_service import MemoryService


INTERNAL_TABLES = {"documents", "conversation_messages"}


class QuestionWorkflow:
    def __init__(self):
        self.engine = create_engine(settings.postgres_url)
        self.document_store = DocumentStore()
        self.memory_service = MemoryService()
        self.athena_service = AthenaService()

    def _describe_postgres_schema(self) -> Dict[str, List[str]]:
        inspector = inspect(self.engine)

        return {
            table_name: [column["name"] for column in inspector.get_columns(table_name)]
            for table_name in inspector.get_table_names()
            if table_name not in INTERNAL_TABLES
        }

    def _format_schema_description(self, schema: Dict[str, List[str]]) -> str:
        if not schema:
            return "no tables available"

        return "\n".join(
            f"- {table_name}({', '.join(columns)})"
            for table_name, columns in schema.items()
        )

    def _format_conversation_context(self, session_id: Optional[str]) -> str:
        if not session_id:
            return ""

        history = self.memory_service.get_recent_messages(session_id)

        return "\n".join(f"{turn['role']}: {turn['content']}" for turn in history)

    def ask(self, question: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        schema = self._describe_postgres_schema()
        athena_tables = self.athena_service.list_tables()
        document_records = self.document_store.list_indexed_document_records()

        initial_state: Dict[str, Any] = {
            "question": question,
            "available_tables": list(schema.keys()) + athena_tables,
            "available_documents": [record["file_name"] for record in document_records],
            "available_document_records": document_records,
            "schema_description": self._format_schema_description(schema),
            "conversation_context": self._format_conversation_context(session_id)
        }

        if session_id:
            initial_state["session_id"] = session_id

        final_state = question_graph.invoke(initial_state)

        return {
            "answer": final_state.get("final_answer"),
            "route": final_state.get("route"),
            "sql": final_state.get("sql"),
            "sources": final_state.get("sources", [])
        }
