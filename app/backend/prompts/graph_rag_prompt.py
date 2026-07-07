from typing import Any, Dict, List


GRAPH_RAG_SYSTEM_PROMPT = (
    "You are a healthcare knowledge assistant that reasons about relationships "
    "between clinical concepts such as diseases, medications, procedures, and "
    "risk factors. Use only the provided graph facts and document evidence, "
    "and explain how the concepts are connected."
)


def build_graph_rag_prompt(
    question: str,
    graph_facts: List[Dict[str, str]],
    chunks: List[Dict[str, Any]]
) -> str:
    facts_text = "\n".join(
        f"- {fact['source']} --{fact['relationship']}--> {fact['target']} "
        f"(from: {fact.get('evidence') or 'unknown'})"
        for fact in graph_facts
    ) or "no graph relationships found"

    evidence_text = "\n\n".join(
        f"[Source: {chunk.get('file_name', 'unknown')}]\n{chunk['text']}"
        for chunk in chunks
    ) or "no document evidence retrieved"

    return f"""
    Graph relationships:
    {facts_text}

    Supporting document evidence:
    {evidence_text}

    Question:
    {question}

    Identify the relevant clinical concepts, explain how they relate to
    each other using the graph relationships above (supplemented by the
    document evidence), and answer the question.
    """
