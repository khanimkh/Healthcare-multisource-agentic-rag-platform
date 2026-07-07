from typing import Any, Dict, List


RAG_SYSTEM_PROMPT = (
    "You are a healthcare research assistant. Answer only using the provided "
    "context. If the context does not contain the answer, say you don't have "
    "enough information. Always mention which source(s) you used."
)


def build_rag_prompt(question: str, chunks: List[Dict[str, Any]]) -> str:
    context = "\n\n".join(
        f"[Source: {chunk.get('file_name', 'unknown')}]\n{chunk['text']}"
        for chunk in chunks
    ) or "no context retrieved"

    return f"""
    Context:
    {context}

    Question:
    {question}

    Answer using only the context above and cite the source file name(s).
    """
