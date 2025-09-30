"""Core model classes and decorators for Cosmos ODM."""

from datetime import datetime
from typing import Any, Generic, Optional, TypeVar, Union

from pydantic import BaseModel, ConfigDict, Field

from .types import ContainerSettings, FullTextIndexSpec, VectorIndexSpec, VectorPolicySpec

T = TypeVar("T")
PKType = TypeVar("PKType")


class PK(Generic[PKType]):
    """Partition key type marker for fields."""

    def __init__(self, value: PKType):
        self.value = value

    def __str__(self) -> str:
        return str(self.value)

    def __repr__(self) -> str:
        return f"PK({self.value!r})"

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, PK):
            return self.value == other.value
        return self.value == other

    def __hash__(self) -> int:
        return hash(self.value)


class ETag:
    """ETag type for optimistic concurrency control."""

    def __init__(self, value: str):
        self.value = value

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"ETag({self.value!r})"

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, ETag):
            return self.value == other.value
        return self.value == other

    def __hash__(self) -> int:
        return hash(self.value)


def container(
    name: str,
    partition_key_path: str,
    ttl: int | None = None,
    throughput: int | None = None,
    unique_keys: list[str] | None = None,
    composite_indexes: list[dict[str, Any]] | None = None,
    vector_policy: list[dict[str, Any]] | None = None,
    vector_indexes: list[dict[str, Any]] | None = None,
    full_text_indexes: list[dict[str, Any]] | None = None,
):
    """Decorator to configure container settings for a Document class."""

    def decorator(cls: type["Document"]) -> type["Document"]:
        # Convert dict specs to dataclass instances
        vector_policy_specs = []
        if vector_policy:
            for spec in vector_policy:
                vector_policy_specs.append(VectorPolicySpec(**spec))

        vector_index_specs = []
        if vector_indexes:
            for spec in vector_indexes:
                vector_index_specs.append(VectorIndexSpec(**spec))

        full_text_index_specs = []
        if full_text_indexes:
            for spec in full_text_indexes:
                full_text_index_specs.append(FullTextIndexSpec(**spec))

        settings = ContainerSettings(
            name=name,
            partition_key_path=partition_key_path,
            ttl=ttl,
            throughput=throughput,
            unique_keys=unique_keys,
            composite_indexes=composite_indexes,
            vector_policy=vector_policy_specs,
            vector_indexes=vector_index_specs,
            full_text_indexes=full_text_index_specs,
        )

        cls._container_settings = settings
        return cls

    return decorator


def embeddings(field: str, dest: str, dims: int):
    """Decorator to mark a method as an embedding provider."""

    def decorator(func):
        func._embedding_config = {
            "field": field,
            "dest": dest,
            "dims": dims,
        }
        return func

    return decorator


class Document(BaseModel):
    """Base class for Cosmos DB documents."""

    model_config = ConfigDict(
        populate_by_name=True,
        extra="forbid",
        validate_assignment=True,
        arbitrary_types_allowed=True,
    )

    # Required fields
    id: str = Field(..., description="Document identifier")
    schema_version: int = Field(default=1, description="Schema version for migrations")

    # Optional system fields
    etag: ETag | None = Field(default=None, description="ETag for optimistic concurrency")
    created_at: datetime | None = Field(default=None, description="Creation timestamp")
    updated_at: datetime | None = Field(default=None, description="Last update timestamp")

    # Container settings (set by decorator)
    _container_settings: ContainerSettings | None = None

    def __init__(self, **data: Any):
        super().__init__(**data)

        # Set timestamps if not provided
        now = datetime.utcnow()
        if self.created_at is None:
            self.created_at = now
        if self.updated_at is None:
            self.updated_at = now

    @classmethod
    def get_container_settings(cls) -> ContainerSettings:
        """Get container settings for this document type."""
        if cls._container_settings is None:
            raise ValueError(
                f"No container settings found for {cls.__name__}. "
                f"Use the @container decorator to configure container settings."
            )
        return cls._container_settings

    @classmethod
    def get_partition_key_field(cls) -> str:
        """Get the partition key field name for this document type."""
        settings = cls.get_container_settings()
        pk_path = settings.partition_key_path

        # Convert "/fieldName" to "fieldName"
        if pk_path.startswith("/"):
            pk_path = pk_path[1:]

        return pk_path

    @classmethod
    def get_partition_key_value(cls, doc: "Document") -> Any:
        """Extract partition key value from a document instance."""
        pk_field = cls.get_partition_key_field()

        # Handle nested paths like "tenant/id"
        if "/" in pk_field:
            parts = pk_field.split("/")
            value = doc
            for part in parts:
                value = getattr(value, part)
            return value

        value = getattr(doc, pk_field)

        # Unwrap PK wrapper if present
        if isinstance(value, PK):
            return value.value

        return value

    @property
    def pk(self) -> Any:
        """Get the partition key value for this document."""
        return self.__class__.get_partition_key_value(self)

    def model_dump_cosmos(self) -> dict[str, Any]:
        """Serialize document for Cosmos DB storage."""
        data = self.model_dump(by_alias=True, exclude_none=True)

        # Convert ETag to string
        if "etag" in data and isinstance(data["etag"], ETag):
            data["etag"] = data["etag"].value

        # Convert datetime to ISO format
        for field_name, field_value in data.items():
            if isinstance(field_value, datetime):
                data[field_name] = field_value.isoformat()

        # Ensure partition key field is properly set
        pk_field = self.get_partition_key_field()
        pk_value = self.get_partition_key_value(self)
        data[pk_field] = pk_value

        return data

    @classmethod
    def model_validate_cosmos(cls: type[T], data: dict[str, Any]) -> T:
        """Deserialize document from Cosmos DB data."""
        # Convert string etag to ETag object
        if "etag" in data and isinstance(data["etag"], str):
            data["etag"] = ETag(data["etag"])

        # Convert ISO datetime strings back to datetime objects
        for field_name, field_info in cls.model_fields.items():
            if field_name in data:
                field_type = field_info.annotation
                if field_type == datetime or (
                    hasattr(field_type, "__origin__")
                    and field_type.__origin__ is Union
                    and datetime in field_type.__args__
                ):
                    if isinstance(data[field_name], str):
                        try:
                            data[field_name] = datetime.fromisoformat(data[field_name])
                        except (ValueError, TypeError):
                            pass  # Keep original value if parsing fails

        # Handle PK fields - wrap partition key values in PK objects
        pk_field = cls.get_partition_key_field()
        if pk_field in data and not isinstance(data[pk_field], PK):
            data[pk_field] = PK(data[pk_field])

        return cls.model_validate(data)

    def upgrade(self, from_version: int) -> "Document":
        """Upgrade document from an older schema version."""
        # Default implementation - subclasses can override
        return self

    @classmethod
    async def bind(
        cls: type[T],
        database: str,
        connection_str: str | None = None,
        client_manager: Optional["CosmosClientManager"] = None
    ) -> "Collection[T]":
        """Bind this document type to a collection."""
        from .client import CosmosClientManager
        from .collection import Collection

        if client_manager is None:
            if connection_str is None:
                raise ValueError("Either connection_str or client_manager must be provided")
            client_manager = CosmosClientManager(connection_str)

        return Collection(
            document_type=cls,
            database_name=database,
            client_manager=client_manager
        )
