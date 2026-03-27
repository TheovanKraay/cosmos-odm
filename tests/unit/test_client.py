"""Unit tests for cosmos_odm.client (CosmosClientManager)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from cosmos_odm.client import CosmosClientManager
from cosmos_odm.errors import CosmosODMError


class TestClientInit:
    def test_init_with_connection_string(self):
        mgr = CosmosClientManager(connection_string="AccountEndpoint=https://x;AccountKey=y;")
        assert mgr.connection_string == "AccountEndpoint=https://x;AccountKey=y;"

    def test_init_with_endpoint_and_key(self):
        mgr = CosmosClientManager(endpoint="https://x", key="mykey")
        assert mgr.endpoint == "https://x"
        assert mgr.key == "mykey"

    def test_init_with_endpoint_only_credential_path(self):
        mgr = CosmosClientManager(endpoint="https://x", key=None)
        assert mgr.endpoint == "https://x"
        assert mgr.key is None

    def test_raises_when_no_connection_info(self):
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(CosmosODMError, match="Either connection_string or endpoint"):
                CosmosClientManager(connection_string=None, endpoint=None, key=None)

    @patch.dict("os.environ", {"COSMOS_CONNECTION_STRING": "AccountEndpoint=https://env;AccountKey=k;"})
    def test_env_fallback_connection_string(self):
        mgr = CosmosClientManager()
        assert "env" in mgr.connection_string

    @patch.dict("os.environ", {"COSMOS_ENDPOINT": "https://env-ep"}, clear=False)
    def test_env_fallback_endpoint(self):
        mgr = CosmosClientManager(key="k")
        assert mgr.endpoint == "https://env-ep"


class TestAsyncClient:
    @patch("cosmos_odm.client.AsyncCosmosClient")
    def test_lazy_creation_with_connection_string(self, MockAsyncClient):
        mock_instance = MagicMock()
        MockAsyncClient.from_connection_string.return_value = mock_instance

        mgr = CosmosClientManager(connection_string="AccountEndpoint=https://x;AccountKey=y;")
        assert mgr._async_client is None
        client = mgr.async_client
        assert client is mock_instance
        MockAsyncClient.from_connection_string.assert_called_once()

    @patch("cosmos_odm.client.AsyncCosmosClient")
    def test_lazy_creation_with_endpoint_key(self, MockAsyncClient):
        mock_instance = MagicMock()
        MockAsyncClient.return_value = mock_instance

        mgr = CosmosClientManager(endpoint="https://x", key="mykey")
        client = mgr.async_client
        assert client is mock_instance
        MockAsyncClient.assert_called_once_with("https://x", "mykey")

    @patch("cosmos_odm.client.AsyncCosmosClient")
    def test_lazy_creation_default_credential(self, MockAsyncClient):
        mock_instance = MagicMock()
        MockAsyncClient.return_value = mock_instance

        with patch("azure.identity.aio.DefaultAzureCredential") as MockCred:
            cred_instance = MagicMock()
            MockCred.return_value = cred_instance
            mgr = CosmosClientManager(endpoint="https://x", key=None)
            _ = mgr.async_client
            MockAsyncClient.assert_called_once_with("https://x", cred_instance)


class TestDatabaseCaching:
    @patch("cosmos_odm.client.AsyncCosmosClient")
    def test_get_async_database_caches(self, MockAsyncClient):
        mock_client = MagicMock()
        MockAsyncClient.from_connection_string.return_value = mock_client
        mock_db = MagicMock()
        mock_client.get_database_client.return_value = mock_db

        mgr = CosmosClientManager(connection_string="AccountEndpoint=https://x;AccountKey=y;")
        db1 = mgr.get_async_database("mydb")
        db2 = mgr.get_async_database("mydb")

        assert db1 is db2
        mock_client.get_database_client.assert_called_once_with("mydb")

    @patch("cosmos_odm.client.AsyncCosmosClient")
    def test_get_async_container(self, MockAsyncClient):
        mock_client = MagicMock()
        MockAsyncClient.from_connection_string.return_value = mock_client
        mock_db = MagicMock()
        mock_client.get_database_client.return_value = mock_db
        mock_container = MagicMock()
        mock_db.get_container_client.return_value = mock_container

        mgr = CosmosClientManager(connection_string="AccountEndpoint=https://x;AccountKey=y;")
        c = mgr.get_async_container("mydb", "mycontainer")
        assert c is mock_container
        mock_db.get_container_client.assert_called_once_with("mycontainer")


class TestCloseAndContextManager:
    @patch("cosmos_odm.client.AsyncCosmosClient")
    async def test_close_clears_state(self, MockAsyncClient):
        mock_client = AsyncMock()
        MockAsyncClient.from_connection_string.return_value = mock_client

        mgr = CosmosClientManager(connection_string="AccountEndpoint=https://x;AccountKey=y;")
        _ = mgr.async_client  # force creation
        await mgr.close()

        assert mgr._async_client is None
        assert mgr._async_databases == {}
        mock_client.close.assert_awaited_once()

    @patch("cosmos_odm.client.AsyncCosmosClient")
    async def test_async_context_manager(self, MockAsyncClient):
        mock_client = AsyncMock()
        MockAsyncClient.from_connection_string.return_value = mock_client

        async with CosmosClientManager(
            connection_string="AccountEndpoint=https://x;AccountKey=y;"
        ) as mgr:
            assert isinstance(mgr, CosmosClientManager)
            # Force lazy client creation so close() has something to close
            _ = mgr.async_client

        mock_client.close.assert_awaited_once()
