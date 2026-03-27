"""Unit tests for cosmos_odm.filters (FilterBuilder)."""

import pytest

from cosmos_odm.filters import FilterBuilder


@pytest.fixture
def fb():
    return FilterBuilder()


class TestSimpleEquality:
    def test_single_field(self, fb):
        clause, params = fb.build_filter({"status": "active"})
        assert "c.status = @param0" in clause
        assert {"name": "@param0", "value": "active"} in params

    def test_multiple_fields_and(self, fb):
        clause, params = fb.build_filter({"a": 1, "b": 2})
        assert "AND" in clause
        assert len(params) == 2


class TestComparisonOperators:
    def test_eq(self, fb):
        clause, params = fb.build_filter({"x": {"$eq": 5}})
        assert "c.x = @param0" in clause
        assert {"name": "@param0", "value": 5} in params

    def test_ne(self, fb):
        clause, params = fb.build_filter({"x": {"$ne": 5}})
        assert "c.x != @param0" in clause

    def test_gt(self, fb):
        clause, params = fb.build_filter({"x": {"$gt": 5}})
        assert "c.x > @param0" in clause

    def test_gte(self, fb):
        clause, params = fb.build_filter({"x": {"$gte": 5}})
        assert "c.x >= @param0" in clause

    def test_lt(self, fb):
        clause, params = fb.build_filter({"x": {"$lt": 5}})
        assert "c.x < @param0" in clause

    def test_lte(self, fb):
        clause, params = fb.build_filter({"x": {"$lte": 5}})
        assert "c.x <= @param0" in clause


class TestInOperators:
    def test_in(self, fb):
        clause, params = fb.build_filter({"status": {"$in": ["a", "b", "c"]}})
        assert "IN" in clause
        assert len(params) == 3

    def test_nin(self, fb):
        clause, params = fb.build_filter({"status": {"$nin": ["x", "y"]}})
        assert "NOT IN" in clause
        assert len(params) == 2


class TestExists:
    def test_exists_true(self, fb):
        clause, params = fb.build_filter({"x": {"$exists": True}})
        assert "IS_DEFINED(c.x)" in clause
        # $exists should not add a parameter
        assert len(params) == 0

    def test_exists_false(self, fb):
        clause, params = fb.build_filter({"x": {"$exists": False}})
        assert "NOT IS_DEFINED(c.x)" in clause


class TestStringOperators:
    def test_contains(self, fb):
        clause, params = fb.build_filter({"name": {"$contains": "test"}})
        assert "CONTAINS(c.name, @param0)" in clause
        assert {"name": "@param0", "value": "test"} in params

    def test_startswith(self, fb):
        clause, params = fb.build_filter({"name": {"$startswith": "pre"}})
        assert "STARTSWITH(c.name, @param0)" in clause

    def test_endswith(self, fb):
        clause, params = fb.build_filter({"name": {"$endswith": "suf"}})
        assert "ENDSWITH(c.name, @param0)" in clause

    def test_regex_maps_to_contains(self, fb):
        clause, params = fb.build_filter({"name": {"$regex": "pat"}})
        assert "CONTAINS(c.name, @param0)" in clause


class TestCombined:
    def test_combined_operators_same_field(self, fb):
        clause, params = fb.build_filter({"age": {"$gte": 18, "$lt": 65}})
        assert "c.age >= @param0" in clause
        assert "c.age < @param1" in clause
        assert len(params) == 2


class TestEdgeCases:
    def test_empty_filter_produces_1_eq_1(self, fb):
        clause, params = fb.build_filter({})
        assert clause == "1=1"
        assert params == []

    def test_unsupported_operator_raises(self, fb):
        with pytest.raises(ValueError, match="Unsupported operator"):
            fb.build_filter({"x": {"$bad": 1}})

    def test_values_are_parameterized(self, fb):
        clause, params = fb.build_filter({"x": "val"})
        # The value should only appear in params, never interpolated in the clause
        assert "val" not in clause
        assert any(p["value"] == "val" for p in params)
