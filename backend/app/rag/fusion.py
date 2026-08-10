"""Reciprocal rank fusion — pure arithmetic, no I/O, no LLM.

Merges any number of independently-ranked candidate-id lists (e.g. a
pgvector similarity ranking and a Postgres full-text-search ranking) into a
single fused ranking. This is the deterministic core of hybrid retrieval
(see docs/ARCHITECTURE.md section 7 and the project's hard rule that
retrieval ranking is never computed by an LLM).

    score(id) = sum over lists containing id of  1 / (k + rank_in_list)

where `rank_in_list` is the 1-based position of `id` within that list, and
`k` is the rank constant (60 is the commonly used default, e.g. in
Elasticsearch's RRF implementation).
"""
from __future__ import annotations

DEFAULT_RANK_CONSTANT = 60


def reciprocal_rank_fusion(
    ranked_lists: list[list[str]], k: int = DEFAULT_RANK_CONSTANT
) -> list[tuple[str, float]]:
    """Fuses `ranked_lists` (each a list of ids, best-first) into a single
    ranking. Returns `(id, score)` pairs sorted by descending fused score,
    deduplicated by id. An id that appears in multiple lists accumulates a
    contribution from each."""
    scores: dict[str, float] = {}
    for ranked_list in ranked_lists:
        for rank, item_id in enumerate(ranked_list, start=1):
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k + rank)

    return sorted(scores.items(), key=lambda pair: pair[1], reverse=True)
