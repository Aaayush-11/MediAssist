from __future__ import annotations

import re
from typing import Any

from rank_bm25 import BM25Okapi

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    """Lowercase the text and extract alphanumeric terms."""
    return _TOKEN_PATTERN.findall(text.lower())


class BM25Retriever:
    """Keyword retriever using BM25Okapi over a collection of documents."""

    def __init__(self, documents: list[dict[str, Any]]) -> None:
        """Validate documents and build the BM25 index.

        Each document must be a dict with a unique ``id`` and a non-empty
        string ``text``. All original keys are retained for search results.
        """
        if not isinstance(documents, list):
            raise TypeError(
                f"documents must be a list of dicts, got {type(documents).__name__}."
            )

        seen_ids: set[Any] = set()
        for index, document in enumerate(documents):
            if not isinstance(document, dict):
                raise TypeError(
                    f"documents[{index}] must be a dict, got {type(document).__name__}."
                )
            if "id" not in document or document["id"] is None:
                raise ValueError(f"documents[{index}] is missing an 'id'.")
            doc_id = document["id"]
            try:
                hash(doc_id)
            except TypeError as exc:
                raise TypeError(
                    f"documents[{index}]['id'] must be hashable, "
                    f"got {type(doc_id).__name__}."
                ) from exc
            if doc_id in seen_ids:
                raise ValueError(f"Duplicate document id: {doc_id!r} at documents[{index}].")
            seen_ids.add(doc_id)

            if "text" not in document:
                raise ValueError(f"documents[{index}] is missing 'text'.")
            text = document["text"]
            if not isinstance(text, str):
                raise TypeError(
                    f"documents[{index}]['text'] must be a string, got {type(text).__name__}."
                )
            if not text.strip():
                raise ValueError(f"documents[{index}]['text'] is empty or whitespace-only.")

        self._documents: list[dict[str, Any]] = list(documents)
        self._bm25: BM25Okapi | None = None
        if self._documents:
            tokenized = [tokenize(doc["text"]) for doc in self._documents]
            if not any(tokenized):
                raise ValueError("No searchable alphanumeric terms found in any document text.")
            self._bm25 = BM25Okapi(tokenized)

    def __len__(self) -> int:
        """Return the number of indexed documents."""
        return len(self._documents)

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Return up to ``top_k`` documents with non-zero BM25 scores, best first.

        Each result contains ``id``, ``score``, and the original document metadata.
        """
        if not isinstance(query, str):
            raise TypeError(f"query must be a string, got {type(query).__name__}.")
        if not query.strip():
            raise ValueError("query must not be empty or whitespace-only.")
        if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k < 1:
            raise ValueError("top_k must be a positive integer.")

        if self._bm25 is None:
            return []

        query_tokens = tokenize(query)
        if not query_tokens:
            return []

        scores = self._bm25.get_scores(query_tokens)
        ranked = sorted(
            (
                (index, float(score))
                for index, score in enumerate(scores)
                if score != 0
            ),
            key=lambda item: (-item[1], item[0]),
        )

        results: list[dict[str, Any]] = []
        for index, score in ranked[:top_k]:
            result = dict(self._documents[index])
            result["score"] = score
            results.append(result)
        return results