from __future__ import annotations

import math
import uuid
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse
from qdrant_client.models import Distance, PointStruct, VectorParams

from src.config import settings
from src.retrieval.embeddings import EmbeddingService


class VectorStoreError(Exception):
    """Raised when a Qdrant operation fails or returns an unexpected result."""


class QdrantVectorStore:
    """Thin wrapper around QdrantClient for storing and searching embeddings."""

    def __init__(
        self,
        embedding_service: EmbeddingService | None = None,
        collection_name: str | None = None,
    ) -> None:
        self.url: str = settings.qdrant_url
        self.collection_name: str = collection_name or settings.qdrant_collection
        self._embedding_service: EmbeddingService | None = embedding_service
        self._vector_size: int | None = None
        self._client = QdrantClient(url=self.url)

    @property
    def vector_size(self) -> int:
        """Embedding dimension from EmbeddingService (resolved lazily, then cached)."""
        if self._vector_size is None:
            if self._embedding_service is None:
                self._embedding_service = EmbeddingService()
            self._vector_size = self._embedding_service.get_embedding_dimension()
        return self._vector_size

    def _wrap(self, action: str, exc: Exception) -> VectorStoreError:
        """Build a meaningful error for a failed Qdrant operation."""
        if isinstance(exc, UnexpectedResponse):
            detail = f"HTTP {exc.status_code}: {exc.content!r}"
        else:
            detail = str(exc)
        return VectorStoreError(
            f"Failed to {action} (collection '{self.collection_name}', "
            f"Qdrant at {self.url}): {detail}"
        )

    def _validate_vector(self, vector: Any, label: str) -> None:
        """Ensure a vector is a list of finite numbers with the expected dimension."""
        if not isinstance(vector, list):
            raise TypeError(f"{label} must be a list of floats, got {type(vector).__name__}.")
        if len(vector) != self.vector_size:
            raise ValueError(
                f"{label} has dimension {len(vector)}, expected {self.vector_size}."
            )
        for position, value in enumerate(vector):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(
                    f"{label}[{position}] must be a numeric value, "
                    f"got {type(value).__name__}."
                )
            if not math.isfinite(value):
                raise ValueError(
                    f"{label}[{position}] must be finite, got {value}."
                )

    @staticmethod
    def _validate_point_id(point_id: Any, label: str) -> None:
        """Qdrant point IDs must be non-negative integers or UUID strings."""
        if isinstance(point_id, bool):
            raise TypeError(f"{label} must be an int or UUID string, got bool.")
        if isinstance(point_id, int):
            if point_id < 0:
                raise ValueError(f"{label} must be non-negative.")
            return
        if isinstance(point_id, str):
            try:
                uuid.UUID(point_id)
            except ValueError as exc:
                raise ValueError(f"{label} '{point_id}' is not a valid UUID string.") from exc
            return
        raise TypeError(f"{label} must be an int or UUID string, got {type(point_id).__name__}.")

    def collection_exists(self) -> bool:
        """Return True if the configured collection exists."""
        try:
            return bool(self._client.collection_exists(self.collection_name))
        except (UnexpectedResponse, ResponseHandlingException) as exc:
            raise self._wrap("check collection existence", exc) from exc

    def create_collection(self) -> None:
        """Create the collection (cosine distance). Raises if it already exists."""
        if self.collection_exists():
            raise VectorStoreError(
                f"Collection '{self.collection_name}' already exists; "
                "it will not be overwritten."
            )
        try:
            self._client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE),
            )
        except (UnexpectedResponse, ResponseHandlingException) as exc:
            raise self._wrap("create collection", exc) from exc

    def ensure_collection(self) -> bool:
        """Create the collection if missing; return True if created, False if it existed.

        An existing collection is never modified, but its vector size and
        distance are verified against the expected configuration.
        """
        if not self.collection_exists():
            self.create_collection()
            return True

        try:
            info = self._client.get_collection(self.collection_name)
        except (UnexpectedResponse, ResponseHandlingException) as exc:
            raise self._wrap("read collection info", exc) from exc

        vectors = info.config.params.vectors
        if not isinstance(vectors, VectorParams):
            raise VectorStoreError(
                f"Collection '{self.collection_name}' uses named or unexpected vector "
                "configuration; expected a single unnamed vector."
            )
        if vectors.size != self.vector_size:
            raise VectorStoreError(
                f"Collection '{self.collection_name}' has vector size {vectors.size}, "
                f"expected {self.vector_size}."
            )
        if vectors.distance != Distance.COSINE:
            raise VectorStoreError(
                f"Collection '{self.collection_name}' uses distance {vectors.distance}, "
                "expected cosine."
            )
        return False

    def upsert_documents(
        self,
        vectors: list[list[float]],
        payloads: list[dict[str, Any]],
        ids: list[int | str] | None = None,
    ) -> list[int | str]:
        """Upsert vectors with metadata payloads and return the point IDs used.

        If ``ids`` is omitted, random UUID strings are generated.
        """
        if not isinstance(vectors, list) or not isinstance(payloads, list):
            raise TypeError("vectors and payloads must be lists.")
        if len(vectors) != len(payloads):
            raise ValueError(
                f"vectors ({len(vectors)}) and payloads ({len(payloads)})" 
		"must have the same length."
            )
        if ids is not None:
            if not isinstance(ids, list):
                raise TypeError("ids must be a list or None.")
            if len(ids) != len(vectors):
                raise ValueError(
                    f"ids ({len(ids)}) and vectors ({len(vectors)}) must have the same length."
                )
            for index, point_id in enumerate(ids):
                self._validate_point_id(point_id, f"ids[{index}]")
            if len(set(ids)) != len(ids):
                raise ValueError("ids must be unique.")
        if not vectors:
            return []

        point_ids: list[int | str] = (
            list(ids) if ids is not None else [str(uuid.uuid4()) for _ in vectors]
        )

        for index, (vector, payload) in enumerate(zip(vectors, payloads)):
            self._validate_vector(vector, f"vectors[{index}]")
            if not isinstance(payload, dict):
                raise TypeError(
                    f"payloads[{index}] must be a dict, got {type(payload).__name__}."
                )

        points = [
            PointStruct(id=point_id, vector=vector, payload=payload)
            for point_id, vector, payload in zip(point_ids, vectors, payloads)
        ]
        try:
            self._client.upsert(
                collection_name=self.collection_name,
                points=points,
                wait=True,
            )
        except (UnexpectedResponse, ResponseHandlingException) as exc:
            raise self._wrap("upsert documents", exc) from exc
        return point_ids

    def search(self, query_vector: list[float], top_k: int = 5) -> list[dict[str, Any]]:
        """Return up to ``top_k`` matches as dicts with ``id``, ``score`` and ``payload``."""
        if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k < 1:
            raise ValueError("top_k must be a positive integer.")
        self._validate_vector(query_vector, "query_vector")

        try:
            response = self._client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                limit=top_k,
                with_payload=True,
            )
        except (UnexpectedResponse, ResponseHandlingException) as exc:
            raise self._wrap("search", exc) from exc

        return [
            {"id": point.id, "score": point.score, "payload": point.payload or {}}
            for point in response.points
        ]

    def delete_collection(self) -> bool:
        """Delete the collection; return True if Qdrant reports it was deleted."""
        try:
            return bool(self._client.delete_collection(self.collection_name))
        except (UnexpectedResponse, ResponseHandlingException) as exc:
            raise self._wrap("delete collection", exc) from exc

    def close(self) -> None:
        """Close the underlying Qdrant client."""
        self._client.close()