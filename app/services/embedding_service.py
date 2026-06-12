from __future__ import annotations

import hashlib
from typing import Protocol


class EmbeddingProvider(Protocol):
    def embed(self, text: str, dims: int) -> list[float]:
        ...


class HashEmbeddingProvider:
    def embed(self, text: str, dims: int) -> list[float]:
        values: list[float] = []
        for idx in range(dims):
            digest = hashlib.sha256(f"{text}:{idx}".encode("utf-8")).digest()
            number = int.from_bytes(digest[:4], byteorder="big", signed=False)
            values.append((number % 2000) / 1000.0 - 1.0)

        norm = sum(v * v for v in values) ** 0.5
        if norm == 0:
            return values
        return [v / norm for v in values]


class SentenceTransformerEmbeddingProvider:
    def __init__(self, model_name: str) -> None:
        from sentence_transformers import SentenceTransformer  # type: ignore[import-not-found]

        self._model = SentenceTransformer(model_name)

    def embed(self, text: str, dims: int) -> list[float]:
        vector = self._model.encode(text, normalize_embeddings=True).tolist()
        if len(vector) == dims:
            return [float(v) for v in vector]
        if len(vector) > dims:
            return [float(v) for v in vector[:dims]]

        padded = [float(v) for v in vector]
        padded.extend([0.0] * (dims - len(padded)))
        return padded


def build_embedding_provider(provider: str, model_name: str) -> EmbeddingProvider:
    normalized = provider.strip().lower()
    if normalized == "sentence_transformers":
        try:
            return SentenceTransformerEmbeddingProvider(model_name)
        except Exception:
            return HashEmbeddingProvider()

    return HashEmbeddingProvider()