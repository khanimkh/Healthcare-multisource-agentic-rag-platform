from app.backend.prompts.graph_rag_prompt import GRAPH_RAG_SYSTEM_PROMPT, build_graph_rag_prompt


def test_build_graph_rag_prompt_renders_fact_triple():
    graph_facts = [{
        "source": "metformin",
        "target": "type 2 diabetes",
        "relationship": "treat",
        "evidence": "Metformin treats type 2 diabetes."
    }]
    chunks = [{"file_name": "research.txt", "text": "Some evidence."}]

    prompt = build_graph_rag_prompt(
        question="How is metformin related to diabetes?",
        graph_facts=graph_facts,
        chunks=chunks
    )

    assert "metformin --treat--> type 2 diabetes" in prompt
    assert "Metformin treats type 2 diabetes." in prompt
    assert "research.txt" in prompt


def test_build_graph_rag_prompt_with_no_facts_or_chunks():
    prompt = build_graph_rag_prompt(question="anything", graph_facts=[], chunks=[])
    assert "no graph relationships found" in prompt
    assert "no document evidence retrieved" in prompt


def test_build_graph_rag_prompt_handles_missing_evidence():
    graph_facts = [{"source": "a", "target": "b", "relationship": "related_to"}]
    prompt = build_graph_rag_prompt(question="q", graph_facts=graph_facts, chunks=[])
    assert "a --related_to--> b" in prompt
    assert "unknown" in prompt
