from __future__ import annotations

import math
from typing import Any

from sentence_transformers import CrossEncoder

from src.config import settings


class RerankerError(Exception):
    """Raised when the cross-encoder fails to load or to score candidates."""


class CrossEncoderReranker:
    """Reranks retrieval candidates with a ``sentence_transformers.CrossEncoder``."""

    def __init__(
        self,
        model_name: str | None = None,
        device: str | None = None,
        model: CrossEncoder | None = None,
    ) -> None:
        """Configure the reranker; the model itself is loaded lazily.

        Args:
            model_name: Cross-encoder model name. Defaults to
                ``settings.reranker_model``.
            device: Torch device string. Defaults to ``settings.reranker_device``.
            model: Optional preloaded model (for dependency injection and tests).
                When supplied, no model is loaded from ``model_name``.
        """
        self.model_name: str = model_name or settings.reranker_model
        self.device: str = device or settings.reranker_device
        self._model: CrossEncoder | None = model

    @property
    def model(self) -> CrossEncoder:
        """The cross-encoder, loaded on first access and cached.

        Raises:
            RerankerError: If the model cannot be loaded.
        """
        if self._model is None:
            try:
                self._model = CrossEncoder(self.model_name, device=self.device)
            except Exception as exc:
                raise RerankerError(
                    f"Failed to load cross-encoder model '{self.model_name}' "
                    f"on device '{self.device}': {exc}"
                ) from exc
        return self._model

    def rerank(
        self,
        query: str,
        candidates: list[dict[str, Any]],
        top_k: int | None = None,
    ) -> list[dict[str, Any]]:
        """Score candidates against the query and return the best ``top_k``.

        Args:
            query: Non-empty search text.
            candidates: Results from ``HybridRetriever.search()``. Each must be a
                dict whose ``payload["text"]`` is a non-empty string.
            top_k: Maximum number of results to return. Defaults to
                ``settings.top_k``.

        Returns:
            Up to ``top_k`` new dicts, sorted by descending ``rerank_score``, each
            containing all fields of the original candidate plus ``rerank_score``.
            Ties keep the input order. Input dicts are not modified.

        Raises:
            TypeError: If ``query`` is not a string or ``candidates`` is not a list
                of dicts.
            ValueError: If ``query`` is empty, ``top_k`` is not a positive integer,
                or a candidate has no usable ``payload["text"]``.
            RerankerError: If the model fails to load, fails during inference, or
                returns invalid scores.
        """
        if not isinstance(query, str):
            raise TypeError(f"query must be a string, got {type(query).__name__}.")
        if not query.strip():
            raise ValueError("query must not be empty or whitespace-only.")
        if not isinstance(candidates, list):
            raise TypeError(f"candidates must be a list of dicts, got {type(candidates).__name__}.")

        limit = settings.top_k if top_k is None else top_k
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValueError("top_k must be a positive integer.")

        if not candidates:
            return []

        texts: list[str] = []
        for index, candidate in enumerate(candidates):
            texts.append(self._extract_text(candidate, index))

        pairs = [(query, text) for text in texts]
        try:
            raw_scores = self.model.predict(pairs)
        except RerankerError:
            raise
        except Exception as exc:
            raise RerankerError(
                f"Cross-encoder '{self.model_name}' failed to score {len(pairs)} "
                f"candidate(s): {exc}"
            ) from exc

        try:
            scores = [float(score) for score in raw_scores]
        except (TypeError, ValueError) as exc:
            raise RerankerError(
                f"Cross-encoder '{self.model_name}' returned scores that are not numeric: {exc}"
            ) from exc
        if len(scores) != len(candidates):
            raise RerankerError(
                f"Cross-encoder '{self.model_name}' returned {len(scores)} score(s) "
                f"for {len(candidates)} candidate(s)."
            )
        if not all(math.isfinite(score) for score in scores):
            raise RerankerError(f"Cross-encoder '{self.model_name}' returned non-finite scores.")

        order = sorted(range(len(candidates)), key=lambda index: (-scores[index], index))
        results: list[dict[str, Any]] = []
        for index in order[:limit]:
            item = dict(candidates[index])
            item["rerank_score"] = scores[index]
            results.append(item)
        return results

    @staticmethod
    def _extract_text(candidate: Any, index: int) -> str:
        """Return ``candidate["payload"]["text"]`` or raise a descriptive error."""
        if not isinstance(candidate, dict):
            raise TypeError(f"candidates[{index}] must be a dict, got {type(candidate).__name__}.")
        payload = candidate.get("payload")
        if not isinstance(payload, dict):
            raise ValueError(f"candidates[{index}] is missing a 'payload' dict.")
        text = payload.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"candidates[{index}]['payload']['text'] must be a non-empty string.")
        return text
