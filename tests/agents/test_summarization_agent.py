# NOTE: SummarizationAgent.__init__ constructs LLMService and OpenSearchVectorStore,
# both of which need boto3/opensearchpy at import time. _resolve_document() itself
# never touches self, so we bypass __init__ via __new__ rather than mocking AWS
# just to test pure string-matching logic. See docs/testing.md for why.

from app.backend.agents.summarization_agent import SummarizationAgent


def _make_agent() -> SummarizationAgent:
    return SummarizationAgent.__new__(SummarizationAgent)


def test_resolve_document_matches_on_word_overlap():
    agent = _make_agent()
    documents = [{"file_id": "abc", "file_name": "readmission_risk_guideline.txt"}]

    result = agent._resolve_document("What are the readmission risk factors?", documents)

    assert result == documents[0]


def test_resolve_document_returns_none_below_threshold():
    agent = _make_agent()
    documents = [{"file_id": "abc", "file_name": "unrelated_topic.txt"}]

    result = agent._resolve_document("What is the weather today?", documents)

    assert result is None


def test_resolve_document_returns_none_for_empty_list():
    agent = _make_agent()
    assert agent._resolve_document("any question", []) is None


def test_resolve_document_picks_best_match_among_several():
    agent = _make_agent()
    documents = [
        {"file_id": "a", "file_name": "lab_result_thresholds.txt"},
        {"file_id": "b", "file_name": "healthcare_insurance_policy.txt"}
    ]

    result = agent._resolve_document(
        "What are the lab result thresholds for risk?",
        documents
    )

    assert result["file_id"] == "a"
