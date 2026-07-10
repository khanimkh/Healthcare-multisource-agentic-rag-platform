# NOTE: the fuzzy document-resolution logic used to be SummarizationAgent._resolve_document(),
# a private method requiring the __new__ constructor-bypass trick to test without
# constructing LLMService/OpenSearchVectorStore (which need boto3/opensearchpy at import
# time). It was later extracted to tools/document_resolution.resolve_document() — a plain,
# dependency-free function shared with ClassificationAgent — so this test now imports it
# directly and no longer needs the constructor workaround. See docs/testing.md.

from app.backend.tools.document_resolution import resolve_document


def test_resolve_document_matches_on_word_overlap():
    documents = [{"file_id": "abc", "file_name": "readmission_risk_guideline.txt"}]

    result = resolve_document("What are the readmission risk factors?", documents)

    assert result == documents[0]


def test_resolve_document_returns_none_below_threshold():
    documents = [{"file_id": "abc", "file_name": "unrelated_topic.txt"}]

    result = resolve_document("What is the weather today?", documents)

    assert result is None


def test_resolve_document_returns_none_for_empty_list():
    assert resolve_document("any question", []) is None


def test_resolve_document_picks_best_match_among_several():
    documents = [
        {"file_id": "a", "file_name": "lab_result_thresholds.txt"},
        {"file_id": "b", "file_name": "healthcare_insurance_policy.txt"}
    ]

    result = resolve_document(
        "What are the lab result thresholds for risk?",
        documents
    )

    assert result["file_id"] == "a"
