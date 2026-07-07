from typing import List


DOCUMENT_CATEGORIES: List[str] = [
    "clinical guideline",
    "patient report",
    "claims dataset",
    "healthcare policy",
    "research publication",
    "lab result",
    "administrative document",
    "unknown"
]

CLASSIFICATION_SYSTEM_PROMPT = (
    "You are a healthcare content classifier. Return only the category name, "
    "nothing else."
)


def build_document_classification_prompt(text: str) -> str:
    categories = "\n".join(f"- {category}" for category in DOCUMENT_CATEGORIES)

    return f"""
    Classify the following healthcare content into exactly one category:
    {categories}

    Return only the category name.

    Content:
    {text[:4000]}
    """


def build_structured_classification_prompt(columns: List[str]) -> str:
    categories = "\n".join(f"- {category}" for category in DOCUMENT_CATEGORIES)
    column_list = ", ".join(columns)

    return f"""
    Classify the following structured healthcare dataset into exactly one category:
    {categories}

    Return only the category name.

    Columns:
    {column_list}
    """
