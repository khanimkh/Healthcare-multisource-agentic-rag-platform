from typing import Optional


SUMMARY_SYSTEM_PROMPT = (
    "You are a healthcare summarization assistant. Produce clear, concise "
    "summaries for business and clinical readers, preserving key facts and "
    "figures without adding information that is not present in the source."
)


def build_summary_prompt(text: str, instructions: Optional[str] = None) -> str:
    task = instructions or "Summarize the content in a few clear paragraphs."

    return f"""
    {task}

    Content:
    {text}
    """
