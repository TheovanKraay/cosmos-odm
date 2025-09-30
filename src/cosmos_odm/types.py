"""Type definitions for Cosmos ODM."""

from dataclasses import dataclass
from typing import Any, Generic, TypeVar

T = TypeVar("T")


@dataclass
class RUMetrics:
    """Request Unit consumption metrics."""

    request_charge: float
    activity_id: str
    session_token: str | None = None


@dataclass
class QueryPage(Generic[T]):
    """A page of query results with metadata."""

    items: list[T]
    continuation_token: str | None
    ru_metrics: RUMetrics


@dataclass
class SearchResults(Generic[T]):
    """Search results with scores and metadata."""

    items: list[T]
    scores: list[float] | None = None
    continuation_token: str | None = None
    ru_metrics: RUMetrics | None = None


@dataclass
class PatchOp:
    """Patch operation for document updates."""

    op: str  # "add", "remove", "replace", "set", "incr"
    path: str
    value: Any = None


@dataclass
class VectorPolicySpec:
    """Vector embedding policy specification."""

    path: str
    data_type: str = "float32"
    dimensions: int = 1536
    distance_function: str = "cosine"


@dataclass
class VectorIndexSpec:
    """Vector index specification."""

    path: str
    type: str = "flat"  # "flat", "quantizedFlat", "diskAnn"


@dataclass
class FullTextIndexSpec:
    """Full-text index specification."""

    paths: list[str]


@dataclass
class ContainerSettings:
    """Container configuration settings."""

    name: str
    partition_key_path: str
    ttl: int | None = None
    throughput: int | None = None
    unique_keys: list[str] | None = None
    composite_indexes: list[dict[str, Any]] | None = None
    vector_policy: list[VectorPolicySpec] | None = None
    vector_indexes: list[VectorIndexSpec] | None = None
    full_text_indexes: list[FullTextIndexSpec] | None = None
