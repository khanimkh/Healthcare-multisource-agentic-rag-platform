from app.backend.prompts.rag_prompt import RAG_SYSTEM_PROMPT, build_rag_prompt


def test_system_prompt_requires_context_grounding():
    assert "provided" in RAG_SYSTEM_PROMPT.lower()
    assert "source" in RAG_SYSTEM_PROMPT.lower()


def test_build_rag_prompt_includes_chunk_text_and_source():
    chunks = [{"file_name": "policy.txt", "text": "Some retrieved content."}]
    prompt = build_rag_prompt(question="What does the policy say?", chunks=chunks)

    assert "policy.txt" in prompt
    assert "Some retrieved content." in prompt
    assert "What does the policy say?" in prompt


def test_build_rag_prompt_with_no_chunks_does_not_crash():
    prompt = build_rag_prompt(question="anything", chunks=[])
    assert "no context retrieved" in prompt


def test_build_rag_prompt_handles_missing_file_name():
    chunks = [{"text": "content with no file_name key"}]
    prompt = build_rag_prompt(question="q", chunks=chunks)
    assert "unknown" in prompt
