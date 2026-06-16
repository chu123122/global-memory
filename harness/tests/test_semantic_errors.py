"""Tests for semantic error contracts."""
from __future__ import annotations

import json
import sqlite3
import tempfile
import urllib.error
import unittest
from pathlib import Path

from harness.semantic.embed import SemanticError, embed_texts, validate_embedding_response, validate_ollama_endpoint
from harness.semantic.index import ensure_index_compatible, open_readonly


class SemanticErrorContractTests(unittest.TestCase):
    def test_non_loopback_ollama_endpoint_is_explicit_error(self) -> None:
        with self.assertRaises(SemanticError) as ctx:
            validate_ollama_endpoint("http://example.com:11434/api/embed")
        self.assertEqual(ctx.exception.error_code, "NON_LOOPBACK_OLLAMA_ENDPOINT")


    def test_loopback_variants_are_allowed_by_embed_validator(self) -> None:
        validate_ollama_endpoint("http://localhost:9999/custom/embed")
        validate_ollama_endpoint("http://127.0.0.1:11434/api/embed")
        validate_ollama_endpoint("http://[::1]:11434/api/embed")

    def test_embed_texts_rejects_non_loopback_before_network(self) -> None:
        with self.assertRaises(SemanticError) as ctx:
            embed_texts(["x"], endpoint="http://example.com:11434/api/embed")
        self.assertEqual(ctx.exception.error_code, "NON_LOOPBACK_OLLAMA_ENDPOINT")

    def test_embed_texts_ollama_unavailable_error_code(self) -> None:
        import unittest.mock as mock

        with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("down")):
            with self.assertRaises(SemanticError) as ctx:
                embed_texts(["x"], endpoint="http://127.0.0.1:11434/api/embed")
        self.assertEqual(ctx.exception.error_code, "OLLAMA_UNAVAILABLE")

    def test_embed_texts_bad_json_error_code(self) -> None:
        import unittest.mock as mock

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return b"not json"

        with mock.patch("urllib.request.urlopen", return_value=Response()):
            with self.assertRaises(SemanticError) as ctx:
                embed_texts(["x"], endpoint="http://127.0.0.1:11434/api/embed")
        self.assertEqual(ctx.exception.error_code, "OLLAMA_BAD_RESPONSE")

    def test_embed_texts_missing_embeddings_error_code(self) -> None:
        import unittest.mock as mock

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return json.dumps({"model": "bge-m3"}).encode("utf-8")

        with mock.patch("urllib.request.urlopen", return_value=Response()):
            with self.assertRaises(SemanticError) as ctx:
                embed_texts(["x"], endpoint="http://127.0.0.1:11434/api/embed")
        self.assertEqual(ctx.exception.error_code, "OLLAMA_BAD_RESPONSE")

    def test_embedding_dimension_mismatch_is_explicit_error(self) -> None:
        with self.assertRaises(SemanticError) as ctx:
            validate_embedding_response([[0.1, 0.2]], expected_dim=1024)
        self.assertEqual(ctx.exception.error_code, "EMBEDDING_DIMENSION_MISMATCH")

    def test_missing_sqlite_schema_is_explicit_error(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "empty.sqlite"
            sqlite3.connect(db).close()
            with self.assertRaises(SemanticError) as ctx:
                open_readonly(db)
        self.assertEqual(ctx.exception.error_code, "SQLITE_SCHEMA_MISSING")

    def test_index_model_mismatch_is_explicit_error(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        conn.execute("INSERT INTO meta(key, value) VALUES ('model', 'other-model')")
        with self.assertRaises(SemanticError) as ctx:
            ensure_index_compatible(conn, expected_model="bge-m3")
        self.assertEqual(ctx.exception.error_code, "INDEX_MODEL_MISMATCH")


if __name__ == "__main__":
    unittest.main()
