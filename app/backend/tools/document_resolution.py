from pathlib import Path
from typing import Dict, List, Optional


def resolve_document(
    question: str,
    available_documents: List[Dict[str, str]]
) -> Optional[Dict[str, str]]:
    question_lower = question.lower()
    best_document = None
    best_score = 0.0

    for document in available_documents:
        stem = Path(document["file_name"]).stem.lower().replace("_", " ").replace("-", " ")
        words = [word for word in stem.split() if len(word) > 2]

        if not words:
            continue

        score = sum(1 for word in words if word in question_lower) / len(words)

        if score > best_score:
            best_score = score
            best_document = document

    return best_document if best_score >= 0.5 else None
