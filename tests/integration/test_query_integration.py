"""Integration tests for query operations against Cosmos DB Emulator.

These tests require a running Cosmos DB Emulator.
Run with: pytest tests/integration/ -v -m integration
"""

import pytest

from cosmos_odm.model import PK

from .conftest import IntegrationTestDoc


pytestmark = [pytest.mark.integration, pytest.mark.asyncio(loop_scope="session")]


class TestQueryIntegration:
    """Query execution and result validation tests."""

    async def test_query_with_parameters(self, test_collection):
        """Test parameterized SQL query execution."""
        # Create test documents
        for i in range(3):
            doc = IntegrationTestDoc(
                category=PK("query-test"),
                title=f"Query Doc {i}",
                content=f"Content {i}",
                score=float(i),
            )
            await test_collection.create(doc)

        # Query with parameters
        results = []
        async for page in test_collection.query(
            sql="SELECT * FROM c WHERE c.category = @category",
            parameters={"category": "query-test"},
            cross_partition=True,
        ):
            results.extend(page.items)

        assert len(results) == 3

    async def test_find_query(self, test_collection):
        """Test find() query builder."""
        for i in range(3):
            doc = IntegrationTestDoc(
                category=PK("find-test"),
                title=f"Find Doc {i}",
                content=f"Content {i}",
            )
            await test_collection.create(doc)

        results = await test_collection.find(
            "c.category = @category", category="find-test"
        ).to_list()
        assert len(results) == 3

    async def test_find_one(self, test_collection):
        """Test find_one returns first matching document."""
        doc = IntegrationTestDoc(
            category=PK("findone-test"),
            title="Only One",
            content="Single doc",
        )
        await test_collection.create(doc)

        result = await test_collection.find_one(
            "c.category = @category", category="findone-test"
        )
        assert result is not None
        assert result.title == "Only One"

    async def test_count_documents(self, test_collection):
        """Test document counting."""
        for i in range(5):
            doc = IntegrationTestDoc(
                category=PK("count-test"),
                title=f"Count Doc {i}",
            )
            await test_collection.create(doc)

        count = await test_collection.count_documents(
            "c.category = @category", category="count-test"
        )
        assert count == 5
