"""Local Ollama embedding helpers for semantic retrieval."""
from __future__ import annotations

import array
import json
import math
import urllib.error
import urllib.request
from urllib.parse import urlparse

from harness.semantic.errors import SemanticError

DEFAULT_OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embed"
DEFAULT_MODEL = "bge-m3"
DEFAULT_DIM = 1024


def validate_ollama_endpoint(url: str) -> None:
    parsed = urlparse(url)
    host = parsed.hostname or ""
    if parsed.scheme != "http" or host not in {"127.0.0.1", "localhost", "::1"}:
        raise SemanticError("NON_LOOPBACK_OLLAMA_ENDPOINT", f"Ollama endpoint must be loopback http: {url}")


def validate_embedding_response(vectors: list[list[float]], *, expected_dim: int = DEFAULT_DIM) -> None:
    for idx, vector in enumerate(vectors):
        if len(vector) != expected_dim:
            raise SemanticError(
                "EMBEDDING_DIMENSION_MISMATCH",
                f"Embedding {idx} has dimension {len(vector)}, expected {expected_dim}",
            )


def normalize_vector(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(float(v) * float(v) for v in vector))
    if norm <= 0:
        raise SemanticError("EMBEDDING_ZERO_NORM", "Embedding vector has zero norm")
    return [float(v) / norm for v in vector]


def vector_to_blob(vector: list[float]) -> bytes:
    return array.array("f", vector).tobytes()


def blob_to_vector(blob: bytes) -> list[float]:
    values = array.array("f")
    values.frombytes(blob)
    return [float(v) for v in values]


def embed_texts(
    texts: list[str],
    *,
    model: str = DEFAULT_MODEL,
    endpoint: str = DEFAULT_OLLAMA_EMBED_URL,
    expected_dim: int = DEFAULT_DIM,
    timeout: float = 60.0,
) -> list[list[float]]:
    validate_ollama_endpoint(endpoint)
    if not texts:
        return []
    payload = json.dumps({"model": model, "input": texts}).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise SemanticError("OLLAMA_UNAVAILABLE", f"Ollama embed endpoint unavailable: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise SemanticError("OLLAMA_BAD_RESPONSE", f"Ollama embed response is not JSON: {exc}") from exc
    vectors = data.get("embeddings")
    if vectors is None and "embedding" in data:
        vectors = [data["embedding"]]
    if not isinstance(vectors, list):
        raise SemanticError("OLLAMA_BAD_RESPONSE", "Ollama embed response missing embeddings")
    normalized = [normalize_vector([float(v) for v in vector]) for vector in vectors]
    validate_embedding_response(normalized, expected_dim=expected_dim)
    if len(normalized) != len(texts):
        raise SemanticError("OLLAMA_BAD_RESPONSE", f"Expected {len(texts)} embeddings, got {len(normalized)}")
    return normalized
