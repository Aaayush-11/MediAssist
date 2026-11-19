from __future__ import annotations

from typing import Any

from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse

from src.retrieval.bm25 import BM25Retriever, tokenize
from src.retrieval.embeddings import EmbeddingService
from src.retrieval.hybrid import reciprocal_rank_fusion
from src.retrieval.vector_store import QdrantVectorStore, VectorStoreError

_SCROLL_PAGE_SIZE = 256


class IndexNotInitializedError(RuntimeError):
    """Raised when a search is attempted before the BM25 index has been built."""


def _validate_limit(value: Any, name: str) -> None:
    """Ensure ``value`` is a positive integer (and not a bool)."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} must be a positive integer.")


class HybridRetriever:
    """Combines Qdrant vector search and BM25 keyword search with RRF fusion."""

    def __init__(
        self,
        embedding_service: EmbeddingService,
        vector_store: QdrantVectorStore,
        bm25_top_k: int = 20,
        vector_top_k: int = 20,
    ) -> None:
        """Store dependencies and retrieval limits.

        The BM25 index is not built here; call :meth:`refresh_index` first.

        Args:
            embedding_service: Service used to embed queries.
            vector_store: Qdrant vector store that is searched and scrolled.
            bm25_top_k: Number of BM25 candidates fetched before fusion.
            vector_top_k: Number of vector candidates fetched before fusion.

        Raises:
            TypeError: If a dependency has the wrong type.
            ValueError: If a limit is not a positive integer.
        """
        if not isinstance(embedding_service, EmbeddingService):
            raise TypeError(
                f"embedding_service must be an EmbeddingService, "
                f"got {type(embedding_service).__name__}."
            )
        if not isinstance(vector_store, QdrantVectorStore):
            raise TypeError(
                f"vector_store must be a QdrantVectorStore, got {type(vector_store).__name__}."
            )
        _validate_limit(bm25_top_k, "bm25_top_k")
        _validate_limit(vector_top_k, "vector_top_k")

        self.embedding_service: EmbeddingService = embedding_service
        self.vector_store: QdrantVectorStore = vector_store
        self.bm25_top_k: int = bm25_top_k
        self.vector_top_k: int = vector_top_k
        self._bm25: BM25Retriever | None = None

    def refresh_index(self) -> int:
        """Rebuild the BM25 index from every point in the Qdrant collection.

        Points are read with paginated ``scroll`` (payloads only, no vectors).
        Points whose payload lacks a non-empty string ``text`` with at least one
        searchable term are skipped. The existing index is replaced only after
        the new one has been built successfully, so a failure leaves it intact.

        Returns:
            The number of documents indexed (0 for an empty collection).

        Raises:
            VectorStoreError: If the collection is missing or Qdrant fails.
        """
        store = self.vector_store
        if not store.collection_exists():
            raise VectorStoreError(
                f"Cannot build the BM25 index: collection '{store.collection_name}' "
                f"does not exist in Qdrant at {store.url}. Ingest documents first."
            )

        documents: list[dict[str, Any]] = []
        offset: Any = None
        while True:
            try:
                points, offset = store._client.scroll(
                    collection_name=store.collection_name,
                    limit=_SCROLL_PAGE_SIZE,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False,
                )
            except (UnexpectedResponse, ResponseHandlingException) as exc:
                raise store._wrap("scroll collection", exc) from exc

            for point in points:
                payload = dict(point.payload or {})
                text = payload.get("text")
                if not isinstance(text, str) or not tokenize(text):
                    continue
                documents.append({"id": str(point.id), "text": text, "payload": payload})

            if offset is None:
                break

        new_index = BM25Retriever(documents)
        self._bm25 = new_index
        return len(new_index)

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Run vector and BM25 search and fuse the results with RRF.

        Args:
            query: Non-empty search text.
            top_k: Maximum number of fused results to return.

        Returns:
            Ranked dicts with ``id`` (string point ID), ``payload`` (including
            ``text``, ``source``, ``page`` and ``chunk_index`` when stored),
            ``rrf_score``, and ``vector_score`` / ``bm25_score`` for each
            retriever that returned the document. Payloads come from Qdrant when
            the vector search returned the point, otherwise from the BM25 snapshot.

        Raises:
            TypeError: If ``query`` is not a string.
            ValueError: If ``query`` is empty or ``top_k`` is not positive.
            IndexNotInitializedError: If :meth:`refresh_index` has not been run.
            VectorStoreError: If the Qdrant search fails.
        """
        if not isinstance(query, str):
            raise TypeError(f"query must be a string, got {type(query).__name__}.")
        if not query.strip():
            raise ValueError("query must not be empty or whitespace-only.")
        _validate_limit(top_k, "top_k")

        if self._bm25 is None:
            raise IndexNotInitializedError(
                "The BM25 index has not been built. Call refresh_index() on this "
                "HybridRetriever before calling search()."
            )

        query_vector = self.embedding_service.encode_query(query)
        if hasattr(query_vector, "tolist"):
            query_vector = query_vector.tolist()
        query_vector = list(query_vector)

        vector_hits = self.vector_store.search(query_vector, top_k=self.vector_top_k)
        bm25_hits = self._bm25.search(query, top_k=self.bm25_top_k)

        vector_results: list[dict[str, Any]] = [
            {
                "id": str(hit["id"]),
                "payload": dict(hit["payload"]),
                "vector_score": float(hit["score"]),
            }
            for hit in vector_hits
        ]
        bm25_results: list[dict[str, Any]] = [
            {
                "id": str(hit["id"]),
                "payload": dict(hit.get("payload", {})),
                "bm25_score": float(hit["score"]),
            }
            for hit in bm25_hits
        ]

        fused = reciprocal_rank_fusion([vector_results, bm25_results], top_k=top_k)

        vector_scores = {item["id"]: item["vector_score"] for item in vector_results}
        bm25_scores = {item["id"]: item["bm25_score"] for item in bm25_results}

        results: list[dict[str, Any]] = []
        for item in fused:
            doc_id = item["id"]
            result: dict[str, Any] = {
                "id": doc_id,
                "payload": item["payload"],
                "rrf_score": item["rrf_score"],
            }
            if doc_id in vector_scores:
                result["vector_score"] = vector_scores[doc_id]
            if doc_id in bm25_scores:
                result["bm25_score"] = bm25_scores[doc_id]
            results.append(result)
        return results
