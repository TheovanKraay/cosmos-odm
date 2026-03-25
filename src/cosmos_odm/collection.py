"""Core Collection class for document operations."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Generic, List, Optional, TypeVar

from azure.cosmos import exceptions as cosmos_exceptions
from azure.cosmos import ContainerProxy
from azure.cosmos.aio import ContainerProxy as AsyncContainerProxy

from .client import CosmosClientManager
from .errors import (
    BadQuery,
    ConditionalCheckFailed,
    CosmosODMError,
    CrossPartitionDisallowed,
    NotFound,
    ThroughputExceeded,
)
from .filters import FilterBuilder
from .model import Document, MergeStrategy
from .query import FindQuery, BulkWriter
from .search_native import IndexManager, SearchQueryBuilder
from .types import PatchOp, QueryPage, RUMetrics, SearchResults

T = TypeVar("T", bound=Document)


class Collection(Generic[T]):
    """Collection interface for document operations."""

    def __init__(
        self,
        document_type: type[T],
        database_name: str,
        client_manager: CosmosClientManager
    ):
        self.document_type = document_type
        self.database_name = database_name
        self.client_manager = client_manager
        self._container_settings = document_type.get_container_settings()
        self._search_builder = SearchQueryBuilder()
        self._filter_builder = FilterBuilder()
        self._index_manager = IndexManager()

    @property
    def container_name(self) -> str:
        """Get container name from document settings."""
        return self._container_settings.name

    @property
    def async_container(self) -> AsyncContainerProxy:
        """Get async container proxy."""
        return self.client_manager.get_async_container(
            self.database_name,
            self.container_name
        )

    @property
    def sync_container(self) -> ContainerProxy:
        """Get sync container proxy."""
        return self.client_manager.get_sync_container(
            self.database_name,
            self.container_name
        )

    def _extract_ru_metrics(self, response_headers: dict[str, Any]) -> RUMetrics:
        """Extract RU metrics from response headers."""
        return RUMetrics(
            request_charge=float(response_headers.get("x-ms-request-charge", 0)),
            activity_id=response_headers.get("x-ms-activity-id", ""),
            session_token=response_headers.get("x-ms-session-token")
        )

    def _handle_cosmos_exception(self, ex: cosmos_exceptions.CosmosHttpResponseError) -> None:
        """Convert Cosmos SDK exceptions to ODM exceptions."""
        status_code = ex.status_code
        message = str(ex)
        activity_id = getattr(ex, "activity_id", None)

        if status_code == 404:
            raise NotFound(message, status_code=status_code, activity_id=activity_id)
        elif status_code == 409 or status_code == 412:
            raise ConditionalCheckFailed(message, status_code=status_code, activity_id=activity_id)
        elif status_code == 429:
            retry_after = getattr(ex, "retry_after_milliseconds", None)
            raise ThroughputExceeded(message, retry_after_ms=retry_after,
                                   status_code=status_code, activity_id=activity_id)
        elif status_code == 400:
            if "cross partition" in message.lower():
                raise CrossPartitionDisallowed(message, status_code=status_code, activity_id=activity_id)
            else:
                raise BadQuery(message, status_code=status_code, activity_id=activity_id)
        else:
            raise CosmosODMError(message, status_code=status_code, activity_id=activity_id)

    async def get(self, pk: Any, id: str) -> T:
        """Get document by partition key and id."""
        try:
            # Extract partition key value if it's a PK wrapper
            if hasattr(pk, 'value'):
                pk_value = pk.value
            else:
                pk_value = pk
            
            response = await self.async_container.read_item(
                item=id,
                partition_key=pk_value
            )

            return self.document_type.model_validate_cosmos(response)

        except cosmos_exceptions.CosmosResourceNotFoundError as ex:
            raise NotFound(f"Document with id='{id}' and pk='{pk}' not found") from ex
        except cosmos_exceptions.CosmosHttpResponseError as ex:
            self._handle_cosmos_exception(ex)

    async def create(self, document: T) -> T:
        """Create a new document."""
        # Update timestamps
        document.updated_at = datetime.now(timezone.utc)
        if document.created_at is None:
            document.created_at = document.updated_at

        try:
            data = document.model_dump_cosmos()
            # The partition key is embedded in the document body automatically
            response = await self.async_container.create_item(body=data)

            return self.document_type.model_validate_cosmos(response)

        except cosmos_exceptions.CosmosHttpResponseError as ex:
            self._handle_cosmos_exception(ex)

    async def replace(self, document: T, if_match: str | None = None) -> T:
        """Replace an existing document."""
        document.updated_at = datetime.now(timezone.utc)

        try:
            data = document.model_dump_cosmos()
            kwargs = {}
            if if_match:
                kwargs["etag"] = if_match
                kwargs["match_condition"] = "IfMatch"

            response = await self.async_container.replace_item(
                item=document.id,
                body=data,
                **kwargs
            )

            return self.document_type.model_validate_cosmos(response)

        except cosmos_exceptions.CosmosHttpResponseError as ex:
            self._handle_cosmos_exception(ex)

    async def upsert(self, document: T) -> T:
        """Create or replace a document."""
        document.updated_at = datetime.now(timezone.utc)
        if document.created_at is None:
            document.created_at = document.updated_at

        try:
            data = document.model_dump_cosmos()
            response = await self.async_container.upsert_item(
                body=data
            )

            return self.document_type.model_validate_cosmos(response)

        except cosmos_exceptions.CosmosHttpResponseError as ex:
            self._handle_cosmos_exception(ex)

    async def delete(self, pk: Any, id: str, if_match: str | None = None) -> None:
        """Delete a document."""
        try:
            # Extract partition key value if it's a PK wrapper
            if hasattr(pk, 'value'):
                pk_value = pk.value
            else:
                pk_value = pk
                
            kwargs = {}
            if if_match:
                kwargs["etag"] = if_match
                kwargs["match_condition"] = "IfMatch"

            await self.async_container.delete_item(
                item=id,
                partition_key=pk_value,
                **kwargs
            )

        except cosmos_exceptions.CosmosResourceNotFoundError as ex:
            raise NotFound(f"Document with id='{id}' and pk='{pk}' not found") from ex
        except cosmos_exceptions.CosmosHttpResponseError as ex:
            self._handle_cosmos_exception(ex)

    async def query(
        self,
        sql: str,
        parameters: dict[str, Any] | None = None,
        partition_key: Any | None = None,
        cross_partition: bool = False,
        max_item_count: int | None = None,
        continuation_token: str | None = None
    ) -> AsyncIterator[QueryPage[T]]:
        """Execute SQL query and yield pages of results."""
        try:
            # Convert parameters to proper format
            if parameters:
                if isinstance(parameters, dict):
                    # Convert dict to list format
                    param_list = []
                    for key, value in parameters.items():
                        param_list.append({"name": f"@{key}", "value": value})
                else:
                    # Already in list format (from search methods)
                    param_list = parameters
            else:
                param_list = []
            
            query_kwargs = {
                "query": sql,
                "parameters": param_list,
            }

            if partition_key is not None:
                query_kwargs["partition_key"] = partition_key
            if max_item_count is not None:
                query_kwargs["max_item_count"] = max_item_count
            if continuation_token:
                query_kwargs["continuation_token"] = continuation_token
            # Cross-partition queries are enabled by default when no partition_key is specified

            query_iterable = self.async_container.query_items(**query_kwargs)

            async for page in query_iterable.by_page():
                # Convert AsyncList to list by iterating
                page_items = []
                async for item in page:
                    page_items.append(item)
                
                items = [
                    self.document_type.model_validate_cosmos(item)
                    for item in page_items
                ]

                # Try to get RU metrics from query_iterable since page doesn't have them
                ru_metrics = RUMetrics(
                    request_charge=getattr(query_iterable, "last_request_charge", 0.0),
                    activity_id=getattr(query_iterable, "last_activity_id", ""),
                    session_token=getattr(query_iterable, "last_session_token", None)
                )
                continuation = getattr(page, 'continuation_token', None)

                yield QueryPage(
                    items=items,
                    continuation_token=continuation,
                    ru_metrics=ru_metrics
                )

        except cosmos_exceptions.CosmosHttpResponseError as ex:
            self._handle_cosmos_exception(ex)

    # Enhanced CRUD Operations
    
    async def save(self, document: T) -> T:
        """Save document (upsert operation)."""
        try:
            # Update timestamp
            document.updated_at = datetime.now(timezone.utc)
            
            # Prepare document data
            doc_data = document.model_dump_cosmos()
            
            # Upsert the document
            response = await self.async_container.upsert_item(
                body=doc_data,
                partition_key=document.pk
            )
            
            # Update document with response data and save state
            result = self.document_type.model_validate_cosmos(response)
            result._save_state()
            return result
            
        except cosmos_exceptions.CosmosHttpResponseError as e:
            self._handle_cosmos_exception(e)
    
    async def save_changes(self, document: T) -> Optional[T]:
        """Save only changed fields. Returns None if no changes."""
        if not document.is_changed:
            return None
        
        changes = document.get_changes()
        if not changes:
            return None
        
        # Update timestamp in changes
        changes["updated_at"] = datetime.now(timezone.utc)
        
        # Perform partial update
        updated_doc = await self.update(document.pk, document.id, changes)
        updated_doc._save_state()
        return updated_doc
    
    async def replace_document(self, document: T, *, ignore_etag: bool = False) -> T:
        """Replace entire document."""
        try:
            # Update timestamp
            document.updated_at = datetime.now(timezone.utc)
            
            # Prepare document data
            doc_data = document.model_dump_cosmos()
            
            # Set etag condition if not ignoring
            etag = None if ignore_etag else (document.etag.value if document.etag else None)
            
            # Replace the document
            response = await self.async_container.replace_item(
                item=document.id,
                body=doc_data,
                partition_key=document.pk,
                etag=etag,
                match_condition=None if ignore_etag else "IfMatch"
            )
            
            # Update document with response data and save state
            result = self.document_type.model_validate_cosmos(response)
            result._save_state()
            return result
            
        except cosmos_exceptions.CosmosHttpResponseError as e:
            self._handle_cosmos_exception(e)
    
    async def sync_document(self, document: T, merge_strategy: MergeStrategy = MergeStrategy.REMOTE) -> T:
        """Sync document with database version."""
        # Get latest version from database
        db_doc = await self.get(document.pk, document.id)
        
        if merge_strategy == MergeStrategy.REMOTE:
            # Use remote version, save state
            db_doc._save_state()
            return db_doc
        
        elif merge_strategy == MergeStrategy.LOCAL:
            if not document._state_management_enabled:
                raise ValueError("Local merge strategy requires state management to be enabled")
            
            # Keep local changes, merge with remote
            local_changes = document.get_changes()
            
            # Apply local changes to remote document
            for key, value in local_changes.items():
                if hasattr(db_doc, key):
                    setattr(db_doc, key, value)
            
            # Save the merged document
            return await self.save(db_doc)
        
        else:  # MANUAL
            raise NotImplementedError("Manual merge strategy requires custom implementation")
    
    async def delete_document(self, document: T, *, ignore_etag: bool = False) -> None:
        """Delete document."""
        etag = None if ignore_etag else (document.etag.value if document.etag else None)
        await self.delete(
            document.pk,
            document.id,
            if_match=etag
        )
    
    # Query Interface
    
    def find(self, condition: str = None, **params: Any) -> "FindQuery[T]":
        """Create a query builder for finding documents."""
        from .query import FindQuery
        query = FindQuery(self)
        if condition:
            query = query.where(condition, **params)
        return query
    
    async def find_one(self, condition: str = None, **params: Any) -> Optional[T]:
        """Find first document matching condition."""
        query = self.find(condition, **params)
        return await query.first()
    
    def find_all(self) -> "FindQuery[T]":
        """Find all documents in collection."""
        from .query import FindQuery
        return FindQuery(self)
    
    async def count_documents(self, condition: str = None, **params: Any) -> int:
        """Count documents matching condition."""
        query = self.find(condition, **params)
        return await query.count()
    
    async def exists_documents(self, condition: str = None, **params: Any) -> bool:
        """Check if documents exist matching condition."""
        query = self.find(condition, **params)
        return await query.exists()
    
    # Bulk Operations
    
    def bulk_writer(self, max_concurrency: int = 10) -> "BulkWriter":
        """Create a bulk writer for batch operations.
        
        Args:
            max_concurrency: Maximum number of concurrent operations (default: 10)
        """
        from .query import BulkWriter
        return BulkWriter(self, max_concurrency=max_concurrency)
    
    async def insert_many(self, documents: List[T]) -> List[T]:
        """Insert multiple documents."""
        bulk = self.bulk_writer()
        for doc in documents:
            bulk.insert(doc)
        
        results = await bulk.execute()
        # Return successfully inserted documents
        inserted_docs = []
        for i, result in enumerate(results):
            if result["success"]:
                # Re-fetch the document to get updated system fields
                doc = documents[i]
                updated_doc = await self.get(doc.pk, doc.id)
                inserted_docs.append(updated_doc)
        
        return inserted_docs
    
    async def delete_many(self, condition: str, **params: Any) -> int:
        """Delete multiple documents matching condition."""
        # First find all matching documents
        query = self.find(condition, **params)
        docs_to_delete = await query.to_list()
        
        if not docs_to_delete:
            return 0
        
        # Delete them in bulk
        bulk = self.bulk_writer()
        for doc in docs_to_delete:
            bulk.delete(doc.pk, doc.id)
        
        results = await bulk.execute()
        return sum(1 for result in results if result["success"])

    async def vector_search(
        self,
        vector: list[float],
        vector_path: str = "/content_vector",
        k: int = 10,
        filter: str | dict[str, Any] | None = None,
        partition_key: Any | None = None
    ) -> SearchResults[T]:
        """Perform vector similarity search."""
        sql, parameters = self._search_builder.build_vector_search(
            vector=vector,
            vector_path=vector_path,
            k=k,
            filter=filter,
            filter_builder=self._filter_builder
        )

        items = []
        scores = []
        continuation_token = None
        ru_metrics = None

        async for page in self.query(
            sql=sql,
            parameters=parameters,
            partition_key=partition_key,
            cross_partition=(partition_key is None),
            max_item_count=k
        ):
            items.extend(page.items)
            continuation_token = page.continuation_token
            ru_metrics = page.ru_metrics
            break  # Only take first page for search results

        return SearchResults(
            items=items,
            scores=scores,  # TODO: Extract from projected scores if available
            continuation_token=continuation_token,
            ru_metrics=ru_metrics
        )

    async def full_text_search(
        self,
        text: str,
        fields: list[str] | None = None,
        k: int = 10,
        filter: str | dict[str, Any] | None = None,
        partition_key: Any | None = None
    ) -> SearchResults[T]:
        """Perform full-text search using BM25."""
        if fields is None:
            fields = ["/content"]
        sql, parameters = self._search_builder.build_full_text_search(
            text=text,
            fields=fields,
            k=k,
            filter=filter,
            filter_builder=self._filter_builder
        )

        items = []
        scores = []
        continuation_token = None
        ru_metrics = None

        async for page in self.query(
            sql=sql,
            parameters=parameters,
            partition_key=partition_key,
            cross_partition=(partition_key is None),
            max_item_count=k
        ):
            items.extend(page.items)
            continuation_token = page.continuation_token
            ru_metrics = page.ru_metrics
            break  # Only take first page for search results

        return SearchResults(
            items=items,
            scores=scores,  # TODO: Extract from projected scores if available
            continuation_token=continuation_token,
            ru_metrics=ru_metrics
        )

    async def hybrid_search(
        self,
        text: str,
        vector: list[float],
        fields: list[str] | None = None,
        vector_path: str = "/content_vector",
        k: int = 10,
        weights: list[int] | None = None,
        filter: str | dict[str, Any] | None = None,
        partition_key: Any | None = None
    ) -> SearchResults[T]:
        """Perform hybrid search using RRF (Reciprocal Rank Fusion)."""
        if fields is None:
            fields = ["/content"]
        sql, parameters = self._search_builder.build_hybrid_search(
            text=text,
            vector=vector,
            fields=fields,
            vector_path=vector_path,
            k=k,
            weights=weights,
            filter=filter,
            filter_builder=self._filter_builder
        )

        items = []
        scores = []
        continuation_token = None
        ru_metrics = None

        async for page in self.query(
            sql=sql,
            parameters=parameters,
            partition_key=partition_key,
            cross_partition=(partition_key is None),
            max_item_count=k
        ):
            items.extend(page.items)
            continuation_token = page.continuation_token
            ru_metrics = page.ru_metrics
            break  # Only take first page for search results

        return SearchResults(
            items=items,
            scores=scores,  # TODO: Extract from projected scores if available
            continuation_token=continuation_token,
            ru_metrics=ru_metrics
        )

    async def ensure_indexes(self) -> dict[str, Any]:
        """Ensure vector and full-text indexes are provisioned."""
        # Ensure database and container exist first
        container = await self._get_container()
        database = self.client_manager.get_async_database(self.database_name)
        return await self._index_manager.ensure_indexes(
            container=container,
            database=database,
            container_name=self.container_name,
            settings=self._container_settings
        )

    async def _ensure_database(self) -> None:
        """Ensure database exists."""
        try:
            client = self.client_manager.async_client
            await client.create_database_if_not_exists(self.database_name)
        except Exception as ex:
            raise CosmosODMError(f"Failed to create database '{self.database_name}': {ex}") from ex

    async def _ensure_container(self) -> None:
        """Ensure container exists with proper configuration."""
        try:
            database = self.client_manager.get_async_database(self.database_name)
            
            # Build partition key spec
            partition_key = {
                "paths": [self._container_settings.partition_key_path],
                "kind": "Hash"
            }
            
            # Build container properties
            container_props = {
                "id": self.container_name
            }
            
            # Add TTL if specified
            if self._container_settings.ttl is not None:
                container_props["defaultTtl"] = self._container_settings.ttl
            
            # Add unique keys if specified
            if self._container_settings.unique_keys:
                container_props["uniqueKeyPolicy"] = {
                    "uniqueKeys": [{"paths": [key]} for key in self._container_settings.unique_keys]
                }
            
            # Create container with throughput if specified
            offer_throughput = self._container_settings.throughput
            
            await database.create_container_if_not_exists(
                id=self.container_name,
                partition_key=partition_key,
                offer_throughput=offer_throughput
            )
            
        except Exception as ex:
            raise CosmosODMError(f"Failed to create container '{self.container_name}': {ex}") from ex

    async def _get_container(self) -> AsyncContainerProxy:
        """Get container proxy, ensuring it exists."""
        await self._ensure_database()
        await self._ensure_container()
        return self.async_container

    @property
    def partition_key_path(self) -> str:
        """Get partition key path for queries."""
        return self._container_settings.partition_key_path

    async def patch(
        self,
        pk: Any,
        id: str,
        operations: list[PatchOp],
        if_match: str | None = None
    ) -> T:
        """Patch a document with the given operations."""
        # This will be implemented when we add patch support
        raise NotImplementedError("Patch operations will be implemented in a future version")

    @asynccontextmanager
    async def batch(self, pk: Any):
        """Create a transactional batch for the given partition key."""
        # This will be implemented when we add batch support
        raise NotImplementedError("Batch operations will be implemented in a future version")
