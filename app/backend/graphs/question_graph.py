from langgraph.graph import END, StateGraph

from app.backend.agents.classification_agent import ClassificationAgent
from app.backend.agents.final_answer_agent import FinalAnswerAgent
from app.backend.agents.graph_rag_agent import GraphRAGAgent
from app.backend.agents.rag_agent import RAGAgent
from app.backend.agents.router_agent import RouterAgent
from app.backend.agents.s3_agent import S3Agent
from app.backend.agents.sql_agent import SQLAgent
from app.backend.agents.summarization_agent import SummarizationAgent
from app.backend.services.memory_service import MemoryService
from app.backend.state.state import QuestionState


router_agent = RouterAgent()
sql_agent = SQLAgent()
s3_agent = S3Agent()
rag_agent = RAGAgent()
graph_rag_agent = GraphRAGAgent()
summarization_agent = SummarizationAgent()
classification_agent = ClassificationAgent()
final_answer_agent = FinalAnswerAgent()
memory_service = MemoryService()


def route_question(state: QuestionState) -> QuestionState:
    route = router_agent.route(
        question=state["question"],
        available_tables=state.get("available_tables"),
        available_documents=state.get("available_documents"),
        conversation_context=state.get("conversation_context")
    )

    return {**state, "route": route}


def run_sql(state: QuestionState) -> QuestionState:
    result = sql_agent.answer(
        question=state["question"],
        schema_description=state.get("schema_description", "")
    )

    return {
        **state,
        "tool_answer": str(result["rows"]),
        "sql": result["sql"],
        "sources": []
    }


def run_s3(state: QuestionState) -> QuestionState:
    result = s3_agent.answer(question=state["question"])

    return {
        **state,
        "tool_answer": str(result["rows"]),
        "sql": result["sql"],
        "sources": []
    }


def run_rag(state: QuestionState) -> QuestionState:
    result = rag_agent.answer(question=state["question"])

    return {
        **state,
        "tool_answer": result["answer"],
        "sources": result["sources"]
    }


def run_graph_rag(state: QuestionState) -> QuestionState:
    result = graph_rag_agent.answer(question=state["question"])

    return {
        **state,
        "tool_answer": result["answer"],
        "sources": result["sources"]
    }


def run_summarization(state: QuestionState) -> QuestionState:
    result = summarization_agent.summarize_document(
        question=state["question"],
        available_documents=state.get("available_document_records")
    )

    return {
        **state,
        "tool_answer": result["summary"],
        "sources": [result["document"]] if result.get("document") else []
    }


def run_classification(state: QuestionState) -> QuestionState:
    result = classification_agent.classify_uploaded_document(
        question=state["question"],
        available_documents=state.get("available_document_records")
    )

    return {
        **state,
        "tool_answer": result["category"],
        "sources": [result["document"]] if result.get("document") else []
    }


def compose_final_answer(state: QuestionState) -> QuestionState:
    result = final_answer_agent.compose(
        question=state["question"],
        route=state["route"],
        tool_answer=state.get("tool_answer", ""),
        sources=state.get("sources"),
        sql=state.get("sql")
    )

    session_id = state.get("session_id")
    if session_id:
        memory_service.add_message(session_id, "user", state["question"])
        memory_service.add_message(session_id, "assistant", result["answer"])

    return {**state, "final_answer": result["answer"]}


def select_route(state: QuestionState) -> str:
    return state["route"]


def build_question_graph():
    graph = StateGraph(QuestionState)

    graph.add_node("route_question", route_question)
    graph.add_node("sql", run_sql)
    graph.add_node("s3", run_s3)
    graph.add_node("rag", run_rag)
    graph.add_node("graph_rag", run_graph_rag)
    graph.add_node("summarization", run_summarization)
    graph.add_node("classification", run_classification)
    graph.add_node("final_answer", compose_final_answer)

    graph.set_entry_point("route_question")

    graph.add_conditional_edges(
        "route_question",
        select_route,
        {
            "sql": "sql",
            "s3": "s3",
            "rag": "rag",
            "graph_rag": "graph_rag",
            "summarization": "summarization",
            "classification": "classification"
        }
    )

    for node in ["sql", "s3", "rag", "graph_rag", "summarization", "classification"]:
        graph.add_edge(node, "final_answer")

    graph.add_edge("final_answer", END)

    return graph.compile()


question_graph = build_question_graph()
