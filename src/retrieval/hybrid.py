from __future__ import annotations

from typing import Any


def reciprocal_rank_fusion(
    result_lists: list[list[dict[str, Any]]],
    k: int = 60,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Combine ranked result lists using Reciprocal Rank Fusion (RRF).

    Each document's score is ``sum(1 / (k + rank))`` over every result list in
    which it appears, with ranks starting at 1. Documents are identified by
    their ``id``. Results are sorted by descending ``rrf_score``; ties are
    broken by the order in which each unique ID first appears across the input
    lists.

    Args:
        result_lists: Ranked result lists, best result first. Each result is a
            dict with a non-null, hashable ``id`` plus any other metadata.
        k: RRF constant (positive integer).
        top_k: Maximum number of fused results to return (positive integer).

    Returns:
        Up to ``top_k`` new dicts containing the original metadata of the first
        occurrence of each document, plus ``rrf_score``. Input dictionaries are
        not modified.
    """
    if isinstance(k, bool) or not isinstance(k, int) or k < 1:
        raise ValueError("k must be a positive integer.")
    if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k < 1:
        raise ValueError("top_k must be a positive integer.")
    if not isinstance(result_lists, list):
        raise TypeError(
            f"result_lists must be a list of lists, got {type(result_lists).__name__}."
        )

    # Insertion order of dict preserves first-appearance order of IDs.
    scores: dict[Any, float] = {}
    documents: dict[Any, dict[str, Any]] = {}

    for list_index, results in enumerate(result_lists):
        if not isinstance(results, list):
            raise TypeError(
                f"result_lists[{list_index}] must be a list, got {type(results).__name__}."
            )

        seen_in_list: set[Any] = set()
        for position, result in enumerate(results):
            label = f"result_lists[{list_index}][{position}]"
            if not isinstance(result, dict):
                raise TypeError(f"{label} must be a dict, got {type(result).__name__}.")
            if "id" not in result or result["id"] is None:
                raise ValueError(f"{label} is missing a non-null 'id'.")
            doc_id = result["id"]
            try:
                hash(doc_id)
            except TypeError as exc:
                raise TypeError(
                    f"{label}['id'] must be hashable, got {type(doc_id).__name__}."
                ) from exc
            if doc_id in seen_in_list:
                raise ValueError(
                    f"Duplicate id {doc_id!r} in result_lists[{list_index}] at position {position}."
                )
            seen_in_list.add(doc_id)

            rank = position + 1
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
            if doc_id not in documents:
                documents[doc_id] = result

    first_seen_order = {doc_id: order for order, doc_id in enumerate(scores)}
    ranked_ids = sorted(
        scores,
        key=lambda doc_id: (-scores[doc_id], first_seen_order[doc_id]),
    )

    fused: list[dict[str, Any]] = []
    for doc_id in ranked_ids[:top_k]:
        item = dict(documents[doc_id])
        item["rrf_score"] = scores[doc_id]
        fused.append(item)
    return fused