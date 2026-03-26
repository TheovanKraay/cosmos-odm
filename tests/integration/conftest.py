"""Integration test fixtures for Cosmos DB Emulator.

These tests require a running Cosmos DB Emulator.
Run with: pytest tests/integration/ -v -m integration
"""

import uuid

import pytest
import pytest_asyncio

from cosmos_odm import CosmosClientManager, Collection
from cosmos_odm.model import Document, PK, container

# Emulator well-known credentials
# MUST use 127.0.0.1, NOT localhost — on Windows, localhost resolves to ::1 (IPv6)
# but the Cosmos DB Emulator only binds to IPv4.
EMULATOR_ENDPOINT = "https://127.0.0.1:8081"
EMULATOR_KEY = "C2y6yDjf5/R+ob0N8A7Cgv30VRDJIWEHLM+4QDU5DE2nQ9nDuVTqobD4b8mGGyPMbIZnqyMsEcaGQy67XIw/Jw=="


@container(
    name="integration_test_items",
    partition_key_path="/category",
)
class IntegrationTestDoc(Document):
    """Document model for integration tests."""
    category: PK[str]
    title: str
    content: str = ""
    score: float = 0.0
    active: bool = True
    tags: list[str] = []


@pytest.fixture(scope="session", autouse=True)
def suppress_ssl_warnings():
    """Suppress SSL warnings for emulator's self-signed certificate."""
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def cosmos_client():
    """Singleton Cosmos client for the entire test session."""
    client = CosmosClientManager(
        endpoint=EMULATOR_ENDPOINT,
        key=EMULATOR_KEY,
        connection_verify=False,  # Required for emulator self-signed cert
    )
    async with client:
        yield client


@pytest.fixture
def test_database_name():
    """Generate a unique test database name."""
    return f"test_cosmos_odm_{uuid.uuid4().hex[:8]}"


@pytest_asyncio.fixture(loop_scope="session")
async def test_collection(cosmos_client, test_database_name):
    """Create a test collection, clean up after."""
    collection = Collection(
        document_type=IntegrationTestDoc,
        database_name=test_database_name,
        client_manager=cosmos_client,
    )
    # Ensure database and container exist
    await collection._ensure_database()
    await collection._ensure_container()
    yield collection
    # Cleanup
    try:
        client = cosmos_client.async_client
        await client.delete_database(test_database_name)
    except Exception:
        pass
