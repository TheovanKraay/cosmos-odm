"""Query builder and bulk operations for Cosmos ODM."""

import asyncio
from abc import ABC, abstractmethod
from typing import Any, Dict, Generic, List, Optional, TypeVar, TYPE_CHECKING, Union
from datetime import datetime, timezone

if TYPE_CHECKING:
    from .collection import Collection
    from .model import Document

T = TypeVar("T", bound="Document")


class QueryBuilder(ABC, Generic[T]):
    """Abstract base class for query builders."""
    
    def __init__(self, collection: "Collection[T]"):
        self.collection = collection
        self._conditions: List[str] = []
        self._parameters: Dict[str, Any] = {}
        self._order_by: List[str] = []
        self._skip_count: Optional[int] = None
        self._limit_count: Optional[int] = None
        self._param_counter = 0
    
    def _add_parameter(self, value: Any) -> str:
        """Add parameter and return parameter name."""
        param_name = f"param{self._param_counter}"
        self._parameters[param_name] = value
        self._param_counter += 1
        return f"@{param_name}"
    
    def where(self, condition: str, **params: Any) -> "QueryBuilder[T]":
        """Add WHERE condition."""
        # Replace named parameters with generated ones
        formatted_condition = condition
        for key, value in params.items():
            param_name = self._add_parameter(value)
            formatted_condition = formatted_condition.replace(f"@{key}", param_name)
        
        self._conditions.append(formatted_condition)
        return self
    
    def order_by(self, field: str, ascending: bool = True) -> "QueryBuilder[T]":
        """Add ORDER BY clause."""
        direction = "ASC" if ascending else "DESC"
        self._order_by.append(f"c.{field} {direction}")
        return self
    
    def skip(self, count: int) -> "QueryBuilder[T]":
        """Add OFFSET clause."""
        self._skip_count = count
        return self
    
    def limit(self, count: int) -> "QueryBuilder[T]":
        """Add LIMIT clause."""
        self._limit_count = count
        return self
    
    def _build_sql(self) -> str:
        """Build SQL query from components."""
        sql = "SELECT * FROM c"
        
        if self._conditions:
            sql += " WHERE " + " AND ".join(self._conditions)
        
        if self._order_by:
            sql += " ORDER BY " + ", ".join(self._order_by)
        
        if self._skip_count is not None:
            sql += f" OFFSET {self._skip_count} LIMIT {self._limit_count or 1000000}"
        elif self._limit_count is not None:
            sql += f" OFFSET 0 LIMIT {self._limit_count}"
        
        return sql


class FindQuery(QueryBuilder[T]):
    """Query builder for find operations."""
    
    async def to_list(self) -> List[T]:
        """Execute query and return all results as list."""
        sql = self._build_sql()
        results = []
        
        async for page in self.collection.query(
            sql=sql,
            parameters=self._parameters,
            cross_partition=True
        ):
            results.extend(page.items)
        
        return results
    
    async def first(self) -> Optional[T]:
        """Execute query and return first result."""
        # Temporarily set limit to 1
        original_limit = self._limit_count
        self._limit_count = 1
        
        try:
            sql = self._build_sql()
            
            async for page in self.collection.query(
                sql=sql,
                parameters=self._parameters,
                cross_partition=True,
                max_item_count=1
            ):
                if page.items:
                    return page.items[0]
                break
            
            return None
        finally:
            self._limit_count = original_limit
    
    async def count(self) -> int:
        """Execute query and return count of results."""
        # Build count query
        sql = "SELECT VALUE COUNT(1) FROM c"
        
        if self._conditions:
            sql += " WHERE " + " AND ".join(self._conditions)
        
        # Convert parameters to list format for SDK
        param_list = [
            {"name": f"@{k}" if not k.startswith("@") else k, "value": v}
            for k, v in self._parameters.items()
        ] if self._parameters else []
        
        # Query the container directly to get raw scalar results
        # (collection.query() deserializes items as documents, but COUNT returns an int)
        query_iterable = self.collection.async_container.query_items(
            query=sql,
            parameters=param_list,
            max_item_count=1,
        )
        async for item in query_iterable:
            return item
        
        return 0
    
    async def exists(self) -> bool:
        """Check if any documents match the query."""
        count = await self.count()
        return count > 0


class BulkWriter:
    """Bulk operations writer with configurable concurrency."""
    
    def __init__(self, collection: "Collection", max_concurrency: int = 10):
        """
        Initialize BulkWriter.
        
        Args:
            collection: The collection to perform operations on
            max_concurrency: Maximum number of concurrent operations (default: 10)
        """
        self.collection = collection
        self.max_concurrency = max_concurrency
        self._operations: List[Dict[str, Any]] = []
    
    def insert(self, document: "Document") -> "BulkWriter":
        """Add insert operation."""
        # Update timestamp
        document.updated_at = datetime.now(timezone.utc)
        
        self._operations.append({
            "operation": "create",
            "partition_key": document.pk,
            "item": document.model_dump_cosmos()
        })
        return self
    
    def upsert(self, document: "Document") -> "BulkWriter":
        """Add upsert operation."""
        # Update timestamp
        document.updated_at = datetime.now(timezone.utc)
        
        self._operations.append({
            "operation": "upsert",
            "partition_key": document.pk,
            "item": document.model_dump_cosmos()
        })
        return self
    
    def replace(self, document: "Document", *, ignore_etag: bool = False) -> "BulkWriter":
        """Add replace operation."""
        # Update timestamp
        document.updated_at = datetime.now(timezone.utc)
        
        operation = {
            "operation": "replace",
            "partition_key": document.pk,
            "item": document.model_dump_cosmos()
        }
        
        if not ignore_etag and document.etag:
            operation["etag"] = document.etag.value
        
        self._operations.append(operation)
        return self
    
    def delete(self, partition_key: Any, item_id: str, *, etag: str = None) -> "BulkWriter":
        """Add delete operation."""
        operation = {
            "operation": "delete",
            "partition_key": partition_key,
            "item_id": item_id
        }
        
        if etag:
            operation["etag"] = etag
        
        self._operations.append(operation)
        return self
    
    async def execute(self, *, progress_callback: Optional[callable] = None, batch_size: int = 50) -> List[Dict[str, Any]]:
        """
        Execute all bulk operations with configurable concurrency.
        
        Args:
            progress_callback: Optional callback function called with (completed_count, total_count)
            batch_size: Number of operations to process in each batch for progress reporting
            
        Returns:
            List of operation results with success/failure status
        """
        if not self._operations:
            return []
        
        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(self.max_concurrency)
        results = []
        completed_count = 0
        total_count = len(self._operations)
        
        async def process_operation(operation: Dict[str, Any]) -> Dict[str, Any]:
            """Process a single operation with semaphore control."""
            nonlocal completed_count
            
            async with semaphore:
                try:
                    result = await self._execute_single_operation(operation)
                    operation_result = {
                        "success": True,
                        "operation": operation["operation"],
                        "partition_key": operation["partition_key"],
                        "result": result
                    }
                except Exception as e:
                    operation_result = {
                        "success": False,
                        "operation": operation["operation"],
                        "partition_key": operation["partition_key"],
                        "error": str(e),
                        "error_type": type(e).__name__
                    }
                
                # Update progress
                completed_count += 1
                if progress_callback and completed_count % batch_size == 0:
                    progress_callback(completed_count, total_count)
                
                return operation_result
        
        # Execute all operations concurrently with semaphore limiting concurrency
        tasks = [process_operation(op) for op in self._operations]
        results = await asyncio.gather(*tasks, return_exceptions=False)
        
        # Final progress callback
        if progress_callback:
            progress_callback(completed_count, total_count)
        
        return results
    
    async def _execute_single_operation(self, operation: Dict[str, Any]) -> Any:
        """Execute a single operation."""
        op_type = operation["operation"]
        
        # Extract partition key value if it's a PK object
        partition_key = operation["partition_key"]
        if hasattr(partition_key, 'value'):
            partition_key = partition_key.value
        
        if op_type == "create":
            return await self.collection.async_container.create_item(
                body=operation["item"],
                partition_key=partition_key
            )
        
        elif op_type == "upsert":
            return await self.collection.async_container.upsert_item(
                body=operation["item"],
                partition_key=partition_key
            )
        
        elif op_type == "replace":
            kwargs = {
                "item": operation["item"]["id"],
                "body": operation["item"],
                "partition_key": partition_key
            }
            
            if "etag" in operation:
                kwargs["etag"] = operation["etag"]
                kwargs["match_condition"] = "IfMatch"
            
            return await self.collection.async_container.replace_item(**kwargs)
        
        elif op_type == "delete":
            kwargs = {
                "item": operation["item_id"],
                "partition_key": partition_key
            }
            
            if "etag" in operation:
                kwargs["etag"] = operation["etag"]
                kwargs["match_condition"] = "IfMatch"
            
            return await self.collection.async_container.delete_item(**kwargs)
        
        else:
            raise ValueError(f"Unknown operation type: {op_type}")