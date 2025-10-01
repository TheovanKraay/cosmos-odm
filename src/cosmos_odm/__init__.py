"""Cosmos ODM: Production-grade Azure Cosmos DB Core (SQL) ODM.

A modern, async-first ODM for Azure Cosmos DB with native vector and full-text search support.
"""

__version__ = "0.1.0"

from .client import CosmosClientManager
from .collection import Collection
from .errors import (
    BadQuery,
    ConditionalCheckFailed,
    CosmosODMError,
    CrossPartitionDisallowed,
    FullTextIndexMissing,
    NotFound,
    PartitionKeyMismatch,
    ThroughputExceeded,
    VectorIndexMissing,
)
from .model import Document, ETag, PK, MergeStrategy, container, embeddings
from .query import QueryBuilder, FindQuery, BulkWriter
from .types import QueryPage, RUMetrics, SearchResults

__all__ = [
    # Core classes
    "Document",
    "Collection",
    "CosmosClientManager",

    # Query interface
    "QueryBuilder",
    "FindQuery",
    "BulkWriter",

    # Types and decorators
    "container",
    "PK",
    "ETag",
    "MergeStrategy",
    "SearchResults",
    "QueryPage",
    "RUMetrics",

    # Exceptions
    "CosmosODMError",
    "ConditionalCheckFailed",
    "ThroughputExceeded",
    "PartitionKeyMismatch",
    "NotFound",
    "BadQuery",
    "CrossPartitionDisallowed",
    "VectorIndexMissing",
    "FullTextIndexMissing",
]
