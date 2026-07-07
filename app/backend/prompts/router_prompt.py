from typing import List, Optional


ROUTES: List[str] = ["sql", "s3", "rag", "graph_rag", "summarization", "classification"]

ROUTER_SYSTEM_PROMPT = (
    "You are the routing agent for a healthcare multi-source assistant. "
    f"Choose exactly one route from: {', '.join(ROUTES)}. "
    "Return only the route name, nothing else."
)


def build_router_prompt(
    question: str,
    available_tables: Optional[List[str]] = None,
    available_documents: Optional[List[str]] = None,
    conversation_context: Optional[str] = None
) -> str:
    tables = ", ".join(available_tables) if available_tables else "none"
    documents = ", ".join(available_documents) if available_documents else "none"
    history = conversation_context or "none"

    return f"""
    Available structured tables: {tables}
    Available documents: {documents}
    Previous conversation context: {history}

    Routing rules:
    - Use "sql" for aggregations, filters, or statistics over structured tables stored in the application database.
    - Use "s3" for aggregations, filters, or statistics over large structured datasets uploaded by the user and queried through Amazon Athena.
    - Use "rag" for questions about document content, policies, or guidelines.
    - Use "graph_rag" for questions about relationships between clinical concepts.
    - Use "summarization" when the user asks to summarize a document or result.
    - Use "classification" when the user asks what type or category something is.

    Question:
    {question}
    """
