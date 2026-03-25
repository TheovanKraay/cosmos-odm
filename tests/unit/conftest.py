"""Shared fixtures for cosmos-odm unit tests."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from cosmos_odm.model import Document, PK, ETag, container
from cosmos_odm.types import ContainerSettings


@container(
    name="test_items",
    partition_key_path="/category",
    vector_policy=[{"path": "/embedding", "data_type": "float32", "dimensions": 4}],
    vector_indexes=[{"path": "/embedding", "type": "flat"}],
    full_text_indexes=[{"paths": ["/title", "/content"]}],
)
class SampleDoc(Document):
    category: PK[str]
    title: str
    content: str = ""
    score: float = 0.0
    active: bool = True
    tags: list[str] = []
    metadata: dict = {}
    embedding: list[float] = []


@pytest.fixture
def sample_doc():
    """Create a sample document."""
    return SampleDoc(
        category=PK("books"),
        title="Test Title",
        content="Test content",
        score=4.5,
        active=True,
        tags=["python", "testing"],
        metadata={"key": "value"},
        embedding=[0.1, 0.2, 0.3, 0.4],
    )


@pytest.fixture
def mock_client_manager():
    """Create a mock CosmosClientManager."""
    manager = MagicMock()
    mock_container = AsyncMock()
    manager.get_async_container.return_value = mock_container
    mock_db = MagicMock()
    manager.get_async_database.return_value = mock_db
    return manager


@pytest.fixture
def mock_container_proxy(mock_client_manager):
    """Return the mock async container proxy from the mock client manager."""
    return mock_client_manager.get_async_container.return_value
