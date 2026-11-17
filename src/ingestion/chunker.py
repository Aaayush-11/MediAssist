from __future__ import annotations

import uuid
from typing import Any


class TextChunker:
    """Splits page-level text into overlapping character-based chunks."""

    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 64) -> None:
        """Validate and store the chunking configuration.

        Args:
            chunk_size: Maximum number of characters per chunk (positive integer).
            chunk_overlap: Number of characters shared by consecutive chunks
                (positive integer, smaller than ``chunk_size``).
        """
        if isinstance(chunk_size, bool) or not isinstance(chunk_size, int) or chunk_size < 1:
            raise ValueError("chunk_size must be a positive integer.")
        if (
            isinstance(chunk_overlap, bool)
            or not isinstance(chunk_overlap, int)
            or chunk_overlap < 1
        ):
            raise ValueError("chunk_overlap must be a positive integer.")
        if chunk_overlap >= chunk_size:
            raise ValueError(
                f"chunk_overlap ({chunk_overlap}) must be smaller than "
                f"chunk_size ({chunk_size})."
            )
        self.chunk_size: int = chunk_size
        self.chunk_overlap: int = chunk_overlap

    def chunk_documents(self, documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Split page-level documents into overlapping chunks.

        Args:
            documents: Dicts with ``source`` (non-empty str), ``page``
                (positive int) and ``text`` (non-empty str), as produced by
                ``PDFLoader``.

        Returns:
            A list of dicts with ``id`` (UUID string), ``text``, ``source``,
            ``page`` and ``chunk_index`` (zero-based within the page). Input
            documents are not modified.

        Raises:
            TypeError: If the input or a field has the wrong type.
            ValueError: If a field is missing, empty, or out of range.
        """
        if not isinstance(documents, list):
            raise TypeError(
                f"documents must be a list of dicts, got {type(documents).__name__}."
            )

        for index, document in enumerate(documents):
            self._validate_document(document, index)

        chunks: list[dict[str, Any]] = []
        for document in documents:
            source: str = document["source"]
            page: int = document["page"]
            for chunk_index, chunk_text in enumerate(self._split_text(document["text"])):
                chunks.append(
                    {
                        "id": str(uuid.uuid4()),
                        "text": chunk_text,
                        "source": source,
                        "page": page,
                        "chunk_index": chunk_index,
                    }
                )
        return chunks

    @staticmethod
    def _validate_document(document: Any, index: int) -> None:
        """Ensure a document has a valid source, page and text."""
        label = f"documents[{index}]"
        if not isinstance(document, dict):
            raise TypeError(f"{label} must be a dict, got {type(document).__name__}.")

        for key in ("source", "page", "text"):
            if key not in document:
                raise ValueError(f"{label} is missing '{key}'.")

        source = document["source"]
        if not isinstance(source, str):
            raise TypeError(f"{label}['source'] must be a string, got {type(source).__name__}.")
        if not source.strip():
            raise ValueError(f"{label}['source'] must not be empty.")

        page = document["page"]
        if isinstance(page, bool) or not isinstance(page, int):
            raise TypeError(f"{label}['page'] must be an integer, got {type(page).__name__}.")
        if page < 1:
            raise ValueError(f"{label}['page'] must be a positive integer.")

        text = document["text"]
        if not isinstance(text, str):
            raise TypeError(f"{label}['text'] must be a string, got {type(text).__name__}.")
        if not text.strip():
            raise ValueError(f"{label}['text'] must not be empty or whitespace-only.")

    def _split_text(self, text: str) -> list[str]:
        """Split text into windows of at most ``chunk_size`` characters."""
        step = self.chunk_size - self.chunk_overlap
        pieces: list[str] = []
        start = 0
        length = len(text)
        while start < length:
            end = min(start + self.chunk_size, length)
            piece = text[start:end].strip()
            if piece.strip():
                pieces.append(piece)
            if end >= length:
                break
            start += step
        return pieces