import math
from typing import List, Set


def precision_at_k(retrieved_ids: List[str], relevant_ids: Set[str], k: int) -> float:
    if k == 0:
        return 0.0

    top_k = retrieved_ids[:k]
    hits = sum(1 for chunk_id in top_k if chunk_id in relevant_ids)

    return hits / k


def recall_at_k(retrieved_ids: List[str], relevant_ids: Set[str]) -> float:
    if not relevant_ids:
        return 0.0

    hits = sum(1 for chunk_id in retrieved_ids if chunk_id in relevant_ids)

    return hits / len(relevant_ids)


def reciprocal_rank(retrieved_ids: List[str], relevant_ids: Set[str]) -> float:
    for rank, chunk_id in enumerate(retrieved_ids, start=1):
        if chunk_id in relevant_ids:
            return 1 / rank

    return 0.0


def ndcg_at_k(retrieved_ids: List[str], relevant_ids: Set[str], k: int) -> float:
    top_k = retrieved_ids[:k]

    dcg = sum(
        1 / math.log2(rank + 1)
        for rank, chunk_id in enumerate(top_k, start=1)
        if chunk_id in relevant_ids
    )

    ideal_hits = min(len(relevant_ids), k)
    idcg = sum(1 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))

    if idcg == 0:
        return 0.0

    return dcg / idcg
