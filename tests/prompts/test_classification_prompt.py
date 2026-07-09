from app.backend.prompts.classification_prompt import (
    CLASSIFICATION_SYSTEM_PROMPT,
    DOCUMENT_CATEGORIES,
    build_document_classification_prompt,
    build_structured_classification_prompt
)


def test_document_categories_list_is_stable():
    assert "clinical guideline" in DOCUMENT_CATEGORIES
    assert "unknown" in DOCUMENT_CATEGORIES
    assert len(DOCUMENT_CATEGORIES) == 8


def test_build_document_classification_prompt_lists_every_category():
    prompt = build_document_classification_prompt("Some clinical text.")
    assert "Some clinical text." in prompt

    for category in DOCUMENT_CATEGORIES:
        assert category in prompt


def test_build_document_classification_prompt_truncates_at_4000_chars():
    long_text = "x" * 5000
    prompt = build_document_classification_prompt(long_text)
    assert "x" * 4000 in prompt
    assert "x" * 4001 not in prompt


def test_build_structured_classification_prompt_includes_columns():
    prompt = build_structured_classification_prompt(["patient_id", "diagnosis"])
    assert "patient_id, diagnosis" in prompt

    for category in DOCUMENT_CATEGORIES:
        assert category in prompt
