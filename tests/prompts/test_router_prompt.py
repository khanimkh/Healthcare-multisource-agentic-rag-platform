from app.backend.prompts.router_prompt import ROUTES, ROUTER_SYSTEM_PROMPT, build_router_prompt


def test_routes_list_is_stable():
    assert ROUTES == ["sql", "s3", "rag", "graph_rag", "summarization", "classification"]


def test_system_prompt_mentions_every_route():
    for route in ROUTES:
        assert route in ROUTER_SYSTEM_PROMPT


def test_build_router_prompt_includes_question():
    prompt = build_router_prompt(question="What are the risk factors for readmission?")
    assert "What are the risk factors for readmission?" in prompt


def test_build_router_prompt_defaults_when_no_context_supplied():
    prompt = build_router_prompt(question="test question")
    assert "Available structured tables: none" in prompt
    assert "Available documents: none" in prompt
    assert "Previous conversation context: none" in prompt


def test_build_router_prompt_includes_supplied_context():
    prompt = build_router_prompt(
        question="test question",
        available_tables=["patients", "visits"],
        available_documents=["policy.txt"],
        conversation_context="user: hi\nassistant: hello"
    )
    assert "patients, visits" in prompt
    assert "policy.txt" in prompt
    assert "user: hi" in prompt
