import json
import statistics
from pathlib import Path
from typing import Any, Dict, List, Set

from app.backend.agents.rag_agent import RAGAgent
from evaluation.metrics import ndcg_at_k, precision_at_k, recall_at_k, reciprocal_rank


EVAL_QUESTIONS_PATH = Path(__file__).parent / "eval_questions.json"
REPORT_PATH = Path(__file__).parent / "evaluation_report.md"
K_VALUES = (1, 3, 5, 10)


def load_eval_questions() -> List[Dict[str, Any]]:
    with open(EVAL_QUESTIONS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def evaluate_question(
    rag_agent: RAGAgent,
    question: str,
    relevant_ids: Set[str],
    k_values
) -> Dict[int, Dict[str, float]]:
    per_k_scores = {}

    for k in k_values:
        chunks = rag_agent.retrieve(question=question, k=k)
        retrieved_ids = [chunk["chunk_id"] for chunk in chunks]

        per_k_scores[k] = {
            "precision": precision_at_k(retrieved_ids, relevant_ids, k),
            "recall": recall_at_k(retrieved_ids, relevant_ids),
            "reciprocal_rank": reciprocal_rank(retrieved_ids, relevant_ids),
            "ndcg": ndcg_at_k(retrieved_ids, relevant_ids, k)
        }

    return per_k_scores


def run_evaluation(k_values=K_VALUES) -> Dict[int, Dict[str, float]]:
    rag_agent = RAGAgent()
    eval_questions = load_eval_questions()

    raw_scores = {
        k: {"precision": [], "recall": [], "reciprocal_rank": [], "ndcg": []}
        for k in k_values
    }

    for item in eval_questions:
        relevant_ids = set(item["relevant_chunk_ids"])
        per_k_scores = evaluate_question(rag_agent, item["question"], relevant_ids, k_values)

        for k, scores in per_k_scores.items():
            for metric_name, value in scores.items():
                raw_scores[k][metric_name].append(value)

    return {
        k: {
            metric_name: statistics.mean(values) if values else 0.0
            for metric_name, values in scores_by_metric.items()
        }
        for k, scores_by_metric in raw_scores.items()
    }


def format_report(averaged_scores: Dict[int, Dict[str, float]]) -> str:
    lines = ["# RAG Retrieval Evaluation Report", ""]
    lines.append("| k | Precision@k | Recall@k | MRR | NDCG@k |")
    lines.append("| --- | --- | --- | --- | --- |")

    for k, scores in sorted(averaged_scores.items()):
        lines.append(
            f"| {k} | {scores['precision']:.3f} | {scores['recall']:.3f} "
            f"| {scores['reciprocal_rank']:.3f} | {scores['ndcg']:.3f} |"
        )

    return "\n".join(lines) + "\n"


def main() -> None:
    averaged_scores = run_evaluation()
    report = format_report(averaged_scores)

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report)

    print(report)


if __name__ == "__main__":
    main()
