"""Tests for the reciprocal-rank-fusion merge logic (app/rag/fusion.py).

This is the deterministic core of hybrid retrieval. It's a pure function —
no DB, no network, no LLM — so it's unit tested directly against
hand-computed expected scores/ordering, per the project's hard rule that
retrieval ranking is real arithmetic, never an LLM call.

`hybrid_search` itself (app/rag/retrieval.py) issues raw pgvector/tsvector
SQL that only real Postgres understands, so it is not exercised here
against the SQLite test DB — that's covered by the RAG smoke test run
manually against the real Supabase Postgres instance (see PR notes), not by
the automated suite.
"""
import pytest

from app.rag.fusion import reciprocal_rank_fusion


def test_reciprocal_rank_fusion_hand_computed_ordering():
    ranked_lists = [["a", "b", "c"], ["c", "a", "b"]]
    fused = reciprocal_rank_fusion(ranked_lists, k=60)

    ids_in_order = [item_id for item_id, _ in fused]
    assert ids_in_order == ["a", "c", "b"]

    scores = dict(fused)
    assert scores["a"] == pytest.approx(1 / 61 + 1 / 62)
    assert scores["b"] == pytest.approx(1 / 62 + 1 / 63)
    assert scores["c"] == pytest.approx(1 / 63 + 1 / 61)


def test_reciprocal_rank_fusion_dedups_across_lists_and_keeps_disjoint_items():
    fused = reciprocal_rank_fusion([["x", "y"], ["z"]], k=60)
    ids = {item_id for item_id, _ in fused}
    assert ids == {"x", "y", "z"}
    assert len(fused) == 3  # no duplicate entries even though merged from 2 lists


def test_reciprocal_rank_fusion_item_only_in_one_list_scores_lower_than_item_in_both():
    # "shared" appears (rank 2) in both lists; "only_a" appears only in list 1 (rank 1).
    fused_scores = dict(
        reciprocal_rank_fusion([["only_a", "shared"], ["only_b", "shared"]], k=60)
    )
    assert fused_scores["shared"] > fused_scores["only_a"]
    assert fused_scores["shared"] > fused_scores["only_b"]


def test_reciprocal_rank_fusion_empty_input_returns_empty():
    assert reciprocal_rank_fusion([]) == []
    assert reciprocal_rank_fusion([[], []]) == []


def test_reciprocal_rank_fusion_higher_rank_constant_compresses_score_spread():
    small_k = dict(reciprocal_rank_fusion([["a", "b"]], k=1))
    large_k = dict(reciprocal_rank_fusion([["a", "b"]], k=1000))

    # Larger k flattens the difference between rank 1 and rank 2.
    assert (small_k["a"] - small_k["b"]) > (large_k["a"] - large_k["b"])
