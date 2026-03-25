"""Cosmos DB client management."""

import os

from azure.cosmos import ContainerProxy, CosmosClient, DatabaseProxy
from azure.cosmos.aio import ContainerProxy as AsyncContainerProxy
from azure.cosmos.aio import CosmosClient as AsyncCosmosClient
from azure.cosmos.aio import DatabaseProxy as AsyncDatabaseProxy

from .errors import CosmosODMError

_UNSET = object()  # Sentinel value


class CosmosClientManager:
    """Manages Cosmos DB client instances and provides database/container access."""

    def __init__(self, connection_string: str | None = None, endpoint: str | None = None,
                 key: str | None = _UNSET, **client_kwargs):
        """Initialize client manager.
        
        Args:
            connection_string: Full connection string for Cosmos DB
            endpoint: Cosmos DB endpoint URL (alternative to connection string)
            key: Cosmos DB account key (alternative to connection string)
            **client_kwargs: Additional arguments passed to CosmosClient
        """
        self.connection_string = connection_string or os.getenv("COSMOS_CONNECTION_STRING")
        self.endpoint = endpoint or os.getenv("COSMOS_ENDPOINT")
        self.key = key if key is not _UNSET else os.getenv("COSMOS_KEY")
        self.client_kwargs = client_kwargs

        if not self.connection_string and not self.endpoint:
            raise CosmosODMError(
                "Either connection_string or endpoint must be provided. "
                "You can also set COSMOS_CONNECTION_STRING or COSMOS_ENDPOINT environment variables."
            )

        self._async_client: AsyncCosmosClient | None = None
        self._sync_client: CosmosClient | None = None
        self._async_databases: dict[str, AsyncDatabaseProxy] = {}
        self._sync_databases: dict[str, DatabaseProxy] = {}
        self._async_credential = None
        self._sync_credential = None

    @property
    def async_client(self) -> AsyncCosmosClient:
        """Get async Cosmos client instance."""
        if self._async_client is None:
            if self.connection_string:
                self._async_client = AsyncCosmosClient.from_connection_string(
                    self.connection_string, **self.client_kwargs
                )
            else:
                if self.key:
                    # Use key-based authentication
                    self._async_client = AsyncCosmosClient(
                        self.endpoint, self.key, **self.client_kwargs
                    )
                else:
                    # Use Default Azure Credentials
                    if self._async_credential is None:
                        from azure.identity.aio import DefaultAzureCredential
                        self._async_credential = DefaultAzureCredential()
                    self._async_client = AsyncCosmosClient(
                        self.endpoint, self._async_credential, **self.client_kwargs
                    )
        return self._async_client

    @property
    def sync_client(self) -> CosmosClient:
        """Get sync Cosmos client instance."""
        if self._sync_client is None:
            if self.connection_string:
                self._sync_client = CosmosClient.from_connection_string(
                    self.connection_string, **self.client_kwargs
                )
            else:
                if self.key:
                    # Use key-based authentication
                    self._sync_client = CosmosClient(
                        self.endpoint, self.key, **self.client_kwargs
                    )
                else:
                    # Use Default Azure Credentials
                    if self._sync_credential is None:
                        from azure.identity import DefaultAzureCredential
                        self._sync_credential = DefaultAzureCredential()
                    self._sync_client = CosmosClient(
                        self.endpoint, self._sync_credential, **self.client_kwargs
                    )
        return self._sync_client

    def get_async_database(self, database_name: str) -> AsyncDatabaseProxy:
        """Get async database proxy."""
        if database_name not in self._async_databases:
            self._async_databases[database_name] = self.async_client.get_database_client(database_name)
        return self._async_databases[database_name]

    def get_sync_database(self, database_name: str) -> DatabaseProxy:
        """Get sync database proxy."""
        if database_name not in self._sync_databases:
            self._sync_databases[database_name] = self.sync_client.get_database_client(database_name)
        return self._sync_databases[database_name]

    def get_async_container(self, database_name: str, container_name: str) -> AsyncContainerProxy:
        """Get async container proxy."""
        database = self.get_async_database(database_name)
        return database.get_container_client(container_name)

    def get_sync_container(self, database_name: str, container_name: str) -> ContainerProxy:
        """Get sync container proxy."""
        database = self.get_sync_database(database_name)
        return database.get_container_client(container_name)

    async def close(self) -> None:
        """Close async client connections."""
        if self._async_client:
            await self._async_client.close()
            self._async_client = None
            self._async_databases.clear()

    async def __aenter__(self) -> "CosmosClientManager":
        """Enter async context manager."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context manager, closing connections."""
        await self.close()

    def __del__(self) -> None:
        """Cleanup on deletion."""
        # Note: We can't call async close() from __del__,
        # so users should explicitly call close() for proper cleanup
