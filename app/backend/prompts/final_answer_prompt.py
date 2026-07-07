from typing import Any, Dict, List, Optional


FINAL_ANSWER_SYSTEM_PROMPT = (
    "You are the final answer composer for a healthcare assistant. Combine "
    "the tool output into one clear answer for the user. Always include "
    "sources when available, note limitations, and never provide direct "
    "medical advice."
)


def build_final_answer_prompt(
    question: str,
    route: str,
    tool_answer: str,
    sources: Optional[List[Dict[str, Any]]] = None,
    sql: Optional[str] = None
) -> str:
    source_lines = "\n".join(
        f"- {source.get('file_name') or source.get('s3_uri') or source}"
        for source in (sources or [])
    ) or "none"

    sql_line = f"Generated SQL: {sql}" if sql else "Generated SQL: none"

    return f"""
    Question:
    {question}

    Route used: {route}
    {sql_line}

    Tool output:
    {tool_answer}

    Sources:
    {source_lines}

    Compose the final answer for the user, including sources and any
    limitations.
    """
