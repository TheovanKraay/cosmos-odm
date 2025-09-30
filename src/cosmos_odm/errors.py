"""Exception hierarchy for Cosmos ODM."""

from typing import Any


class CosmosODMError(Exception):
    """Base exception for all Cosmos ODM errors."""

    def __init__(self, message: str, status_code: int | None = None,
                 activity_id: str | None = None, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.activity_id = activity_id
        self.details = details or {}


class ConditionalCheckFailed(CosmosODMError):
    """Raised when a conditional operation fails (ETag mismatch)."""
    pass


class ThroughputExceeded(CosmosODMError):
    """Raised when request rate is too large (429)."""

    def __init__(self, message: str, retry_after_ms: int | None = None, **kwargs):
        super().__init__(message, **kwargs)
        self.retry_after_ms = retry_after_ms


class PartitionKeyMismatch(CosmosODMError):
    """Raised when partition key doesn't match expectations."""
    pass


class NotFound(CosmosODMError):
    """Raised when a resource is not found (404)."""
    pass


class BadQuery(CosmosODMError):
    """Raised when a query is malformed or invalid."""
    pass


class CrossPartitionDisallowed(CosmosODMError):
    """Raised when cross-partition query is attempted but not allowed."""
    pass


class VectorIndexMissing(CosmosODMError):
    """Raised when vector search is attempted without proper vector index."""

    def __init__(self, message: str, vector_path: str, **kwargs):
        super().__init__(message, **kwargs)
        self.vector_path = vector_path
        self.remediation = (
            f"Ensure vector policy and index are configured for path '{vector_path}'. "
            f"Call await collection.ensure_indexes() to provision required indexes."
        )


class FullTextIndexMissing(CosmosODMError):
    """Raised when full-text search is attempted without proper full-text index."""

    def __init__(self, message: str, text_paths: list[str], **kwargs):
        super().__init__(message, **kwargs)
        self.text_paths = text_paths
        self.remediation = (
            f"Ensure full-text index is configured for paths {text_paths}. "
            f"Call await collection.ensure_indexes() to provision required indexes."
        )
