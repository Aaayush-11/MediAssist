from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from src.ingestion.chunker import TextChunker
from src.ingestion.pdf_loader import PDFLoader
from src.retrieval.embeddings import EmbeddingService
from src.retrieval.vector_store import QdrantVectorStore


class DocumentIngestionPipeline:
    """Loads a PDF, chunks it, embeds the chunks and upserts them into Qdrant."""

    def __init__(
        self,
        pdf_loader: PDFLoader | None = None,
        chunker: TextChunker | None = None,
        embedding_service: EmbeddingService | None = None,
        vector_store: QdrantVectorStore | None = None,
        batch_size: int = 32,
    ) -> None:
        """Wire up pipeline dependencies, creating defaults when not supplied.

        The same ``EmbeddingService`` instance is shared by the pipeline and
        the vector store. If both are supplied, they must be the same instance.

        Args:
            pdf_loader: Optional PDF loader.
            chunker: Optional text chunker.
            embedding_service: Optional embedding service.
            vector_store: Optional Qdrant vector store.
            batch_size: Number of chunks embedded and upserted per batch.

        Raises:
            ValueError: If ``batch_size`` is not a positive integer, or if the
                supplied embedding service differs from the vector store's.
        """
        if isinstance(batch_size, bool) or not isinstance(batch_size, int) or batch_size < 1:
            raise ValueError("batch_size must be a positive integer.")

        self.batch_size: int = batch_size
        self.pdf_loader: PDFLoader = pdf_loader if pdf_loader is not None else PDFLoader()
        self.chunker: TextChunker = chunker if chunker is not None else TextChunker()

        if vector_store is not None:
            store_service = getattr(vector_store, "_embedding_service", None)
            if embedding_service is not None:
                if store_service is not None and store_service is not embedding_service:
                    raise ValueError(
                        "embedding_service must be the same instance used by vector_store."
                    )
                if store_service is None:
                    vector_store._embedding_service = embedding_service
                self.embedding_service: EmbeddingService = embedding_service
            elif store_service is not None:
                self.embedding_service = store_service
            else:
                self.embedding_service = EmbeddingService()
                vector_store._embedding_service = self.embedding_service
            self.vector_store: QdrantVectorStore = vector_store
        else:
            self.embedding_service = (
                embedding_service if embedding_service is not None else EmbeddingService()
            )
            self.vector_store = QdrantVectorStore(embedding_service=self.embedding_service)

    @staticmethod
    def _make_point_id(chunk: dict[str, Any]) -> str:
        """Build a deterministic UUID5 from source, page, chunk_index and text."""
        name = json.dumps(
            [
                chunk["source"],
                chunk["page"],
                chunk["chunk_index"],
                chunk["text"],
            ]
        )
        return str(uuid.uuid5(uuid.NAMESPACE_URL, name))

    def ingest_pdf(self, file_path: str | Path) -> dict[str, Any]:
        """Ingest a PDF into the vector store.

        Args:
            file_path: Path to a ``.pdf`` file.

        Returns:
            A dict with ``source``, ``pages_processed``, ``chunks_created``,
            ``vectors_upserted`` and ``point_ids``.

        Raises:
            TypeError: If ``file_path`` is not a string or Path.
            Exception: Errors from the loader, chunker, embedding service or
                vector store are propagated unchanged.
        """
        if not isinstance(file_path, (str, Path)):
            raise TypeError(
                f"file_path must be a str or Path, got {type(file_path).__name__}."
            )

        source = Path(file_path).name
        pages = self.pdf_loader.load_pdf(file_path)
        chunks = self.chunker.chunk_documents(pages)

        result: dict[str, Any] = {
            "source": source,
            "pages_processed": len(pages),
            "chunks_created": len(chunks),
            "vectors_upserted": 0,
            "point_ids": [],
        }
        if not chunks:
            return result

        self.vector_store.ensure_collection()

        point_ids: list[str] = []
        vectors_upserted = 0
        for start in range(0, len(chunks), self.batch_size):
            batch = chunks[start : start + self.batch_size]
            texts = [chunk["text"] for chunk in batch]
            vectors = self.embedding_service.encode_documents(texts)
            payloads = [
                {
                    "text": chunk["text"],
                    "source": chunk["source"],
                    "page": chunk["page"],
                    "chunk_index": chunk["chunk_index"],
                }
                for chunk in batch
            ]
            batch_ids: list[int | str] = [self._make_point_id(chunk) for chunk in batch]
            used_ids = self.vector_store.upsert_documents(vectors, payloads, batch_ids)
            point_ids.extend(str(point_id) for point_id in used_ids)
            vectors_upserted += len(used_ids)

        result["vectors_upserted"] = vectors_upserted
        result["point_ids"] = point_ids
        return result