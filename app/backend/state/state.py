from typing import Any, Dict, List, Optional, TypedDict


class QuestionState(TypedDict, total=False):
    session_id: str
    question: str
    route: str
    available_tables: List[str]
    available_documents: List[str]
    available_document_records: List[Dict[str, str]]
    schema_description: str
    conversation_context: str
    tool_answer: str
    sources: List[Dict[str, Any]]
    sql: Optional[str]
    final_answer: str
