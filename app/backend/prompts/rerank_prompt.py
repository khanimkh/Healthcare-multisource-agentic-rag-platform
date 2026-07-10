from typing import Any, Dict, List


RERANK_SYSTEM_PROMPT = (
    "You are a relevance-scoring assistant. Given a question and a numbered list "
    "of text passages, return ONLY a JSON array of the passage numbers ordered "
    "from most to least relevant to the question. Example: [3, 1, 2]. "
    "Return nothing except the JSON array."
)


def build_rerank_prompt(question: str, chunks: List[Dict[str, Any]]) -> str:
    passages = "\n\n".join(
        f"[{index}] {chunk['text']}"
        for index, chunk in enumerate(chunks)
    )

    return f"""
    Question:
    {question}

    Passages:
    {passages}

    Return a JSON array of passage numbers, ordered from most to least relevant.
    """
