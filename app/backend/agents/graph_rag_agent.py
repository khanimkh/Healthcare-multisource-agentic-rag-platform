from typing import Any, Dict

from app.backend.agents.rag_agent import RAGAgent
from app.backend.prompts.graph_rag_prompt import GRAPH_RAG_SYSTEM_PROMPT, build_graph_rag_prompt
from app.backend.services.graph_store_service import GraphStoreService
from app.backend.services.llm_service import LLMService
from app.backend.tools.entity_extraction import extract_entities_and_relationships


class GraphRAGAgent:
    def __init__(self):
        self.rag_agent = RAGAgent()
        self.llm_service = LLMService()
        self.graph_store = GraphStoreService()

    def answer(self, question: str, k: int = 5, hops: int = 2) -> Dict[str, Any]:
        extraction = extract_entities_and_relationships(question)
        graph_facts = self.graph_store.find_related(extraction["entities"], hops=hops)

        chunks = self.rag_agent.retrieve(question=question, k=k)

        prompt = build_graph_rag_prompt(
            question=question,
            graph_facts=graph_facts,
            chunks=chunks
        )

        answer = self.llm_service.generate(
            prompt=prompt,
            system_prompt=GRAPH_RAG_SYSTEM_PROMPT,
            max_tokens=800,
            temperature=0.2
        )

        return {
            "answer": answer,
            "sources": [
                {
                    "file_name": chunk.get("file_name"),
                    "file_id": chunk.get("file_id"),
                    "s3_uri": chunk.get("s3_uri")
                }
                for chunk in chunks
            ]
        }
