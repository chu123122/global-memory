"""Regression tests for gm.search query-vector reuse in semantic engine."""
from __future__ import annotations

from unittest import mock

from harness.semantic.engine import query_index, vector_hits, warm_vector_cache
from harness.semantic.query import ChannelHit, ChunkInfo


def test_vector_hits_uses_supplied_query_vector_without_embedding():
    conn = mock.Mock()
    with mock.patch("harness.semantic.engine.embed_texts") as embed_mock, \
        mock.patch("harness.semantic.engine.load_vectors", return_value={"c": [1.0, 0.0]}):
        hits = vector_hits(conn, "q", query_vector=[1.0, 0.0])
    embed_mock.assert_not_called()
    assert hits == [ChannelHit("c", "vector", 1.0, vector_source="bge-m3")]


def test_query_index_passes_supplied_query_vector_to_vector_hits():
    with mock.patch("harness.semantic.engine.open_readonly") as open_mock, \
        mock.patch("harness.semantic.engine.lexical_hits", return_value=[]), \
        mock.patch("harness.semantic.engine.metadata_hits", return_value=[]), \
        mock.patch("harness.semantic.engine.vector_hits", return_value=[ChannelHit("c", "vector", 0.9)]) as vector_mock, \
        mock.patch("harness.semantic.engine.load_chunk_info", return_value={"c": ChunkInfo("c", "docs/a.md", "T1")}):
        conn = mock.Mock()
        open_mock.return_value = conn
        query_index("q", debug=True, query_vector=[1.0, 0.0])
    assert vector_mock.call_args.kwargs["query_vector"] == [1.0, 0.0]


def test_vector_hits_can_use_index_vector_cache_without_reloading(tmp_path):
    index = tmp_path / "semantic.sqlite"
    index.write_text("placeholder", encoding="utf-8")
    conn = mock.Mock()
    with mock.patch("harness.semantic.engine.open_readonly") as open_mock, \
        mock.patch("harness.semantic.engine.load_vectors", return_value={"c": [1.0, 0.0]}) as load_mock:
        open_mock.return_value = mock.Mock()
        first = vector_hits(conn, "q", query_vector=[1.0, 0.0], index_path=index)
        second = vector_hits(conn, "q", query_vector=[1.0, 0.0], index_path=index)
    assert [hit.raw_score for hit in first] == [1.0]
    assert [hit.raw_score for hit in second] == [1.0]
    load_mock.assert_called_once()


def test_warm_vector_cache_loads_by_index_mtime(tmp_path):
    index = tmp_path / "semantic.sqlite"
    index.write_text("placeholder", encoding="utf-8")
    with mock.patch("harness.semantic.engine.open_readonly") as open_mock, \
        mock.patch("harness.semantic.engine.load_vectors", return_value={"a": [1.0], "b": [0.0]}):
        open_mock.return_value = mock.Mock()
        assert warm_vector_cache(index) == 2


def test_vector_hits_numpy_cache_path_if_numpy_available(tmp_path):
    try:
        import numpy  # noqa: F401
    except ModuleNotFoundError:
        return
    index = tmp_path / "semantic.sqlite"
    index.write_text("placeholder", encoding="utf-8")
    conn = mock.Mock()
    with mock.patch("harness.semantic.engine.open_readonly") as open_mock, \
        mock.patch("harness.semantic.engine.load_vectors", return_value={"a": [1.0, 0.0], "b": [0.0, 1.0]}) as load_mock:
        open_mock.return_value = mock.Mock()
        hits = vector_hits(conn, "q", query_vector=[0.0, 1.0], index_path=index, limit=1)
    assert hits[0].chunk_id == "b"
    load_mock.assert_called_once()
