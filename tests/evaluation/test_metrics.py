from evaluation.metrics import ndcg_at_k, precision_at_k, recall_at_k, reciprocal_rank


RETRIEVED = ["a", "b", "c", "d", "e"]
RELEVANT = {"b", "d"}


def test_precision_at_k():
    assert precision_at_k(RETRIEVED, RELEVANT, 5) == 0.4


def test_precision_at_smaller_k():
    assert precision_at_k(RETRIEVED, RELEVANT, 2) == 0.5


def test_precision_at_k_zero_k():
    assert precision_at_k(RETRIEVED, RELEVANT, 0) == 0.0


def test_recall_at_k_full_hit():
    assert recall_at_k(RETRIEVED, RELEVANT) == 1.0


def test_recall_at_k_partial_hit():
    assert recall_at_k(["a", "b", "c"], RELEVANT) == 0.5


def test_recall_at_k_empty_relevant_set():
    assert recall_at_k(RETRIEVED, set()) == 0.0


def test_reciprocal_rank_first_hit_at_rank_two():
    assert reciprocal_rank(RETRIEVED, RELEVANT) == 0.5


def test_reciprocal_rank_no_hits():
    assert reciprocal_rank(RETRIEVED, {"z"}) == 0.0


def test_ndcg_at_k():
    assert round(ndcg_at_k(RETRIEVED, RELEVANT, 5), 4) == 0.6509


def test_ndcg_at_k_empty_relevant_set():
    assert ndcg_at_k(RETRIEVED, set(), 5) == 0.0


def test_ndcg_at_k_perfect_ranking():
    # both relevant chunks ranked first -> NDCG should be 1.0
    assert ndcg_at_k(["b", "d", "a", "c", "e"], RELEVANT, 5) == 1.0
