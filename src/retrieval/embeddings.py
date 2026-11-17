from __future__ import annotations

from sentence_transformers import SentenceTransformer

from src.config import settings

BGE_QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "


class EmbeddingService:
    """Generates normalized BGE embeddings for documents and queries."""

    def __init__(self, batch_size: int = 32) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be at least 1.")
        self.model_name: str = settings.embedding_model
        self.device: str = settings.embedding_device
        self.batch_size: int = batch_size
        # truncate_dim=None keeps the model's full embedding dimension.
        self._model = SentenceTransformer(
            self.model_name,
            device=self.device,
            truncate_dim=None,
        )

    def encode_documents(self, texts: list[str]) -> list[list[float]]:
        """Encode document chunks in batches and return normalized vectors."""
        if not isinstance(texts, list):
            raise TypeError("texts must be a list of strings.")
        if not texts:
            return []

        for index, text in enumerate(texts):
            if not isinstance(text, str):
                raise TypeError(
                    f"texts[{index}] must be a string, got {type(text).__name__}."
                )
            if not text.strip():
                raise ValueError(f"texts[{index}] is empty or whitespace-only.")

        embeddings = self._model.encode(
            texts,
            batch_size=self.batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        vectors: list[list[float]] = embeddings.tolist()

        expected_dim = self.get_embedding_dimension()
        if len(vectors) != len(texts):
            raise RuntimeError(
                f"Expected {len(texts)} embeddings, got {len(vectors)}."
            )
        for index, vector in enumerate(vectors):
            if len(vector) != expected_dim:
                raise RuntimeError(
                    f"Document embedding {index} has dimension {len(vector)}, "
                    f"expected {expected_dim}."
                )
        return vectors

    def encode_query(self, query: str) -> list[float]:
        """Encode a single query with the BGE instruction and return a normalized vector."""
        if not isinstance(query, str):
            raise TypeError(f"query must be a string, got {type(query).__name__}.")
        if not query.strip():
            raise ValueError("query must not be empty or whitespace-only.")

        embedding = self._model.encode(
            BGE_QUERY_INSTRUCTION + query.strip(),
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        vector: list[float] = embedding.tolist()

        expected_dim = self.get_embedding_dimension()
        if len(vector) != expected_dim:
            raise RuntimeError(
                f"Query embedding has dimension {len(vector)}, expected {expected_dim}."
            )
        return vector

    def get_embedding_dimension(self) -> int:
        """Return the embedding dimension of the loaded model."""
        dimension = self._model.get_embedding_dimension()
        if dimension is None:
            raise RuntimeError(
                f"Could not determine embedding dimension for model '{self.model_name}'."
            )
        return int(dimension)