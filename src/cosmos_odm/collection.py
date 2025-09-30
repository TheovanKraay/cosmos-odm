"""Core Collection class for document operations."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Generic, TypeVar

from azure.cosmos import exceptions as cosmos_exceptions
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
from .model import Document
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
            response = await self.async_container.read_item(
                item=id,
                partition_key=pk
            )

            return self.document_type.model_validate_cosmos(response)

        except cosmos_exceptions.CosmosResourceNotFoundError as ex:
            raise NotFound(f"Document with id='{id}' and pk='{pk}' not found") from ex
        except cosmos_exceptions.CosmosHttpResponseError as ex:
            self._handle_cosmos_exception(ex)

    async def create(self, document: T) -> T:
        """Create a new document."""
        # Update timestamps
        from datetime import datetime
        document.updated_at = datetime.utcnow()
        if document.created_at is None:
            document.created_at = document.updated_at

        try:
            data = document.model_dump_cosmos()
            response = await self.async_container.create_item(
                body=data,
                partition_key=document.pk
            )

            return self.document_type.model_validate_cosmos(response)

        except cosmos_exceptions.CosmosHttpResponseError as ex:
            self._handle_cosmos_exception(ex)

    async def replace(self, document: T, if_match: str | None = None) -> T:
        """Replace an existing document."""
        from datetime import datetime
        document.updated_at = datetime.utcnow()

        try:
            data = document.model_dump_cosmos()
            kwargs = {}
            if if_match:
                kwargs["etag"] = if_match
                kwargs["match_condition"] = "IfMatch"

            response = await self.async_container.replace_item(
                item=document.id,
                body=data,
                partition_key=document.pk,
                **kwargs
            )

            return self.document_type.model_validate_cosmos(response)

        except cosmos_exceptions.CosmosHttpResponseError as ex:
            self._handle_cosmos_exception(ex)

    async def upsert(self, document: T) -> T:
        """Create or replace a document."""
        from datetime import datetime
        document.updated_at = datetime.utcnow()
        if document.created_at is None:
            document.created_at = document.updated_at

        try:
            data = document.model_dump_cosmos()
            response = await self.async_container.upsert_item(
                body=data,
                partition_key=document.pk
            )

            return self.document_type.model_validate_cosmos(response)

        except cosmos_exceptions.CosmosHttpResponseError as ex:
            self._handle_cosmos_exception(ex)

    async def delete(self, pk: Any, id: str, if_match: str | None = None) -> None:
        """Delete a document."""
        try:
            kwargs = {}
            if if_match:
                kwargs["etag"] = if_match
                kwargs["match_condition"] = "IfMatch"

            await self.async_container.delete_item(
                item=id,
                partition_key=pk,
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
            query_kwargs = {
                "query": sql,
                "parameters": parameters or [],
                "enable_cross_partition_query": cross_partition,
            }

            if partition_key is not None:
                query_kwargs["partition_key"] = partition_key
            if max_item_count is not None:
                query_kwargs["max_item_count"] = max_item_count
            if continuation_token:
                query_kwargs["continuation_token"] = continuation_token

            query_iterable = self.async_container.query_items(**query_kwargs)

            async for page in query_iterable.by_page():
                items = [
                    self.document_type.model_validate_cosmos(item)
                    for item in page
                ]

                ru_metrics = self._extract_ru_metrics(page.response_headers)
                continuation = page.continuation_token

                yield QueryPage(
                    items=items,
                    continuation_token=continuation,
                    ru_metrics=ru_metrics
                )

        except cosmos_exceptions.CosmosHttpResponseError as ex:
            self._handle_cosmos_exception(ex)

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
        fields: list[str] = ["/content"],
        k: int = 10,
        filter: str | dict[str, Any] | None = None,
        partition_key: Any | None = None
    ) -> SearchResults[T]:
        """Perform full-text search using BM25."""
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
        fields: list[str] = ["/content"],
        vector_path: str = "/content_vector",
        k: int = 10,
        weights: list[int] | None = None,
        filter: str | dict[str, Any] | None = None,
        partition_key: Any | None = None
    ) -> SearchResults[T]:
        """Perform hybrid search using RRF (Reciprocal Rank Fusion)."""
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
        return await self._index_manager.ensure_indexes(
            container=self.async_container,
            settings=self._container_settings
        )

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
