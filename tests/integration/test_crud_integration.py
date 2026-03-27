"""Integration tests for CRUD operations against Cosmos DB Emulator.

These tests require a running Cosmos DB Emulator.
Run with: pytest tests/integration/ -v -m integration
"""

import pytest

from cosmos_odm.model import PK, ETag

from .conftest import IntegrationTestDoc


pytestmark = [pytest.mark.integration, pytest.mark.asyncio(loop_scope="session")]


class TestCRUDIntegration:
    """Full CRUD lifecycle tests against emulator."""

    async def test_create_and_read(self, test_collection):
        """Test creating a document and reading it back."""
        doc = IntegrationTestDoc(
            category=PK("test"),
            title="Integration Test",
            content="Hello from integration test",
        )

        created = await test_collection.create(doc)
        assert created.id == doc.id
        assert created.title == "Integration Test"

        # Read it back
        fetched = await test_collection.get(PK("test"), doc.id)
        assert fetched.id == doc.id
        assert fetched.title == "Integration Test"
        assert fetched.content == "Hello from integration test"

    async def test_upsert(self, test_collection):
        """Test upsert creates then updates."""
        doc = IntegrationTestDoc(
            category=PK("test"),
            title="Upsert Test",
            content="Original",
        )

        # First upsert creates
        result1 = await test_collection.upsert(doc)
        assert result1.title == "Upsert Test"

        # Modify and upsert again
        doc.content = "Updated"
        result2 = await test_collection.upsert(doc)
        assert result2.content == "Updated"

        # Verify final state
        fetched = await test_collection.get(PK("test"), doc.id)
        assert fetched.content == "Updated"

    async def test_replace(self, test_collection):
        """Test replace operation."""
        doc = IntegrationTestDoc(
            category=PK("test"),
            title="Replace Test",
            content="Before replace",
        )
        created = await test_collection.create(doc)

        created.content = "After replace"
        replaced = await test_collection.replace(created)
        assert replaced.content == "After replace"

    async def test_delete(self, test_collection):
        """Test delete operation."""
        doc = IntegrationTestDoc(
            category=PK("test"),
            title="Delete Test",
            content="Will be deleted",
        )
        await test_collection.create(doc)

        # Delete it
        await test_collection.delete(PK("test"), doc.id)

        # Verify it's gone
        from cosmos_odm.errors import NotFound
        with pytest.raises(NotFound):
            await test_collection.get(PK("test"), doc.id)

    async def test_not_found(self, test_collection):
        """Test NotFound error on missing document."""
        from cosmos_odm.errors import NotFound
        with pytest.raises(NotFound):
            await test_collection.get(PK("test"), "nonexistent-id")
