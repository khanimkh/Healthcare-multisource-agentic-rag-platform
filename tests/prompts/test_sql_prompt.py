from app.backend.prompts.sql_prompt import SQL_SYSTEM_PROMPT, build_sql_prompt


def test_system_prompt_requires_read_only_select():
    assert "read-only" in SQL_SYSTEM_PROMPT.lower()
    assert "select" in SQL_SYSTEM_PROMPT.lower()


def test_build_sql_prompt_default_dialect_is_postgresql():
    prompt = build_sql_prompt(question="How many patients?", schema_description="patients(id, age)")
    assert "PostgreSQL" in prompt


def test_build_sql_prompt_custom_dialect_replaces_default():
    prompt = build_sql_prompt(
        question="How many patients?",
        schema_description="patients(id, age)",
        dialect="Amazon Athena (Presto) SQL"
    )
    assert "Amazon Athena (Presto) SQL" in prompt
    assert "PostgreSQL" not in prompt


def test_build_sql_prompt_includes_schema_and_question():
    prompt = build_sql_prompt(question="my question", schema_description="my schema")
    assert "my question" in prompt
    assert "my schema" in prompt
