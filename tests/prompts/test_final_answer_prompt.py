from app.backend.prompts.final_answer_prompt import FINAL_ANSWER_SYSTEM_PROMPT, build_final_answer_prompt


def test_system_prompt_forbids_medical_advice():
    assert "medical advice" in FINAL_ANSWER_SYSTEM_PROMPT.lower()


def test_build_final_answer_prompt_with_sources_and_sql():
    prompt = build_final_answer_prompt(
        question="How many patients?",
        route="sql",
        tool_answer="[{'count': 20}]",
        sources=[{"file_name": "patients.csv"}],
        sql="SELECT COUNT(*) FROM patients"
    )

    assert "How many patients?" in prompt
    assert "Route used: sql" in prompt
    assert "Generated SQL: SELECT COUNT(*) FROM patients" in prompt
    assert "patients.csv" in prompt


def test_build_final_answer_prompt_without_sources_or_sql():
    prompt = build_final_answer_prompt(question="q", route="rag", tool_answer="answer")

    assert "Generated SQL: none" in prompt


def test_build_final_answer_prompt_falls_back_to_s3_uri_when_no_file_name():
    prompt = build_final_answer_prompt(
        question="q",
        route="rag",
        tool_answer="answer",
        sources=[{"s3_uri": "s3://bucket/key.pdf"}]
    )

    assert "s3://bucket/key.pdf" in prompt
