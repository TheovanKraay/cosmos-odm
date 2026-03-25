"""Unit tests for cosmos_odm.search_native (SearchQueryBuilder, IndexManager)."""

import pytest

from cosmos_odm.search_native import SearchQueryBuilder, IndexManager
from cosmos_odm.errors import VectorIndexMissing, FullTextIndexMissing
from cosmos_odm.filters import FilterBuilder
from cosmos_odm.types import VectorPolicySpec, VectorIndexSpec, FullTextIndexSpec


@pytest.fixture
def sqb():
    return SearchQueryBuilder()


@pytest.fixture
def fb():
    return FilterBuilder()


# ---------------------------------------------------------------------------
# SearchQueryBuilder – vector search
# ---------------------------------------------------------------------------

class TestVectorSearch:
    def test_basic_vector_query(self, sqb):
        sql, params = sqb.build_vector_search(
            vector=[0.1, 0.2], vector_path="/embedding", k=5
        )
        assert "TOP @k" in sql
        assert "VectorDistance" in sql
        assert "ORDER BY RANK" in sql
        # Parameters
        param_names = {p["name"] for p in params}
        assert "@k" in param_names
        assert "@vector" in param_names

    def test_vector_search_with_filter_dict(self, sqb, fb):
        sql, params = sqb.build_vector_search(
            vector=[0.1], vector_path="/emb", k=3,
            filter={"status": "active"}, filter_builder=fb
        )
        assert "WHERE" in sql
        assert "@param0" in sql
        assert any(p["name"] == "@param0" and p["value"] == "active" for p in params)

    def test_vector_search_with_string_filter(self, sqb):
        sql, params = sqb.build_vector_search(
            vector=[0.1], vector_path="/emb", k=3,
            filter="c.active = true"
        )
        assert "WHERE c.active = true" in sql


# ---------------------------------------------------------------------------
# SearchQueryBuilder – full-text search
# ---------------------------------------------------------------------------

class TestFullTextSearch:
    def test_single_field(self, sqb):
        sql, params = sqb.build_full_text_search(
            text="hello", fields=["/title"], k=10
        )
        assert "FullTextScore" in sql
        assert "TOP @k" in sql
        assert any(p["name"] == "@text" for p in params)

    def test_multiple_fields(self, sqb):
        sql, params = sqb.build_full_text_search(
            text="hello", fields=["/title", "/content"], k=10
        )
        assert sql.count("FullTextScore") == 2


# ---------------------------------------------------------------------------
# SearchQueryBuilder – hybrid search
# ---------------------------------------------------------------------------

class TestHybridSearch:
    def test_hybrid_includes_rrf(self, sqb):
        sql, params = sqb.build_hybrid_search(
            text="hello", vector=[0.1], fields=["/title"],
            vector_path="/emb", k=5
        )
        assert "RRF" in sql
        assert "FullTextScore" in sql
        assert "VectorDistance" in sql
        param_names = {p["name"] for p in params}
        assert "@text" in param_names
        assert "@vector" in param_names

    def test_hybrid_with_weights(self, sqb):
        sql, params = sqb.build_hybrid_search(
            text="hello", vector=[0.1], fields=["/title"],
            vector_path="/emb", k=5, weights=[1, 2]
        )
        assert "@weights" in sql or any(p["name"] == "@weights" for p in params)
        assert any(p["name"] == "@weights" and p["value"] == [1, 2] for p in params)

    def test_all_queries_parameterized(self, sqb):
        sql, params = sqb.build_hybrid_search(
            text="q", vector=[0.1], fields=["/t"],
            vector_path="/e", k=5
        )
        # Text and vector values must only appear in params, not interpolated
        param_names = {p["name"] for p in params}
        assert "@text" in param_names
        assert "@vector" in param_names
        assert any(p["value"] == "q" for p in params)
        assert any(p["value"] == [0.1] for p in params)


# ---------------------------------------------------------------------------
# IndexManager – build configurations
# ---------------------------------------------------------------------------

class TestIndexManagerBuild:
    def test_build_vector_configuration(self):
        im = IndexManager()
        policy_specs = [VectorPolicySpec(path="/emb", data_type="float32", dimensions=128)]
        index_specs = [VectorIndexSpec(path="/emb", type="flat")]

        policy, indexes = im._build_vector_configuration(policy_specs, index_specs)

        assert policy is not None
        embeddings = policy["vectorEmbeddings"]
        assert len(embeddings) == 1
        assert embeddings[0]["path"] == "/emb"
        assert embeddings[0]["dimensions"] == 128

        assert len(indexes) == 1
        assert indexes[0]["path"] == "/emb"
        assert indexes[0]["type"] == "flat"

    def test_build_full_text_configuration(self):
        im = IndexManager()
        specs = [FullTextIndexSpec(paths=["/title", "/content"])]
        indexes = im._build_full_text_configuration(specs)

        assert len(indexes) == 2
        paths = [idx["path"] for idx in indexes]
        assert "/title" in paths
        assert "/content" in paths


# ---------------------------------------------------------------------------
# IndexManager – validation
# ---------------------------------------------------------------------------

class TestIndexManagerValidation:
    def test_validate_vector_search_support_raises(self):
        im = IndexManager()
        policy = {"vectorIndexes": [{"path": "/other"}]}
        with pytest.raises(VectorIndexMissing):
            im.validate_vector_search_support(policy, "/embedding")

    def test_validate_vector_search_support_ok(self):
        im = IndexManager()
        policy = {"vectorIndexes": [{"path": "/embedding"}]}
        im.validate_vector_search_support(policy, "/embedding")  # should not raise

    def test_validate_full_text_search_support_raises(self):
        im = IndexManager()
        policy = {"fullTextIndexes": []}
        with pytest.raises(FullTextIndexMissing):
            im.validate_full_text_search_support(policy, ["/title"])

    def test_validate_full_text_search_support_ok(self):
        im = IndexManager()
        policy = {"fullTextIndexes": [{"paths": ["/title"]}]}
        im.validate_full_text_search_support(policy, ["/title"])  # should not raise
