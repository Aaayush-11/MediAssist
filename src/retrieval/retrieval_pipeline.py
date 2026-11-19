from __future__ import annotations

from typing import Any

from src.config import settings
from src.retrieval.hybrid_retriever import HybridRetriever
from src.retrieval.reranker import CrossEncoderReranker


class RetrievalPipeline:
    """Runs hybrid retrieval followed by cross-encoder reranking."""

    def __init__(
        self,
        hybrid_retriever: HybridRetriever,
        reranker: CrossEncoderReranker,
    ) -> None:
        """Store the injected retrieval components.

        Args:
            hybrid_retriever: Retriever that produces the initial candidates. Its
                BM25 index must be built with ``refresh_index()`` before searching.
            reranker: Cross-encoder that reorders the candidates.
        """
        self.hybrid_retriever: HybridRetriever = hybrid_retriever
        self.reranker: CrossEncoderReranker = reranker

    def search(self, query: str) -> list[dict[str, Any]]:
        """Retrieve candidates with hybrid search and rerank them.

        Fetches ``settings.rerank_top_k`` candidates from the hybrid retriever,
        then returns the best ``settings.top_k`` after cross-encoder reranking.

        Args:
            query: Non-empty search text.

        Returns:
            The reranked results exactly as returned by the reranker, or an empty
            list if hybrid retrieval found no candidates.

        Raises:
            TypeError: If ``query`` is not a string.
            ValueError: If ``query`` is empty or whitespace-only.
            Exception: Errors from the hybrid retriever or reranker (for example
                ``IndexNotInitializedError``, ``VectorStoreError`` or
                ``RerankerError``) propagate unchanged.
        """
        if not isinstance(query, str):
            raise TypeError(f"query must be a string, got {type(query).__name__}.")
        if not query.strip():
            raise ValueError("query must not be empty or whitespace-only.")

        candidates = self.hybrid_retriever.search(query, top_k=settings.rerank_top_k)
        if not candidates:
            return []

        return self.reranker.rerank(query, candidates, top_k=settings.top_k)
