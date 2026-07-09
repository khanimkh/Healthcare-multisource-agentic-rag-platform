from app.backend.prompts.summary_prompt import SUMMARY_SYSTEM_PROMPT, build_summary_prompt


def test_build_summary_prompt_uses_default_instructions():
    prompt = build_summary_prompt(text="Some long document text.")
    assert "Summarize the content in a few clear paragraphs." in prompt
    assert "Some long document text." in prompt


def test_build_summary_prompt_uses_custom_instructions():
    prompt = build_summary_prompt(text="content", instructions="Summarize in three bullet points.")
    assert "Summarize in three bullet points." in prompt
    assert "Summarize the content in a few clear paragraphs." not in prompt


def test_build_summary_prompt_does_not_truncate_long_text():
    # Regression test: build_summary_prompt used to hard-truncate at 8000 chars.
    # SummarizationAgent now guarantees safe chunk sizes upstream, so this
    # function must pass text through untouched.
    long_text = "x" * 10000
    prompt = build_summary_prompt(text=long_text)
    assert long_text in prompt
