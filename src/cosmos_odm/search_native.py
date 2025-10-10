"""Native search query builders for vector, full-text, and hybrid search in Cosmos DB."""

from typing import TYPE_CHECKING, Any, Optional

from .errors import CosmosODMError, FullTextIndexMissing, VectorIndexMissing
from .types import ContainerSettings, FullTextIndexSpec, VectorIndexSpec, VectorPolicySpec

if TYPE_CHECKING:
    from .filters import FilterBuilder


class SearchQueryBuilder:
    """Builds Cosmos SQL queries for native search operations."""

    def build_vector_search(
        self,
        vector: list[float],
        vector_path: str,
        k: int,
        filter: str | dict[str, Any] | None = None,
        filter_builder: Optional["FilterBuilder"] = None
    ) -> tuple[str, list[dict[str, Any]]]:
        """Build vector similarity search query.
        
        Returns:
            Tuple of (SQL query, parameters)
        """
        # Parameters for the query
        parameters = [
            {"name": "@k", "value": k},
            {"name": "@vector", "value": vector}
        ]

        # Build WHERE clause if filter provided
        where_clause = ""
        if filter:
            if isinstance(filter, dict) and filter_builder:
                filter_sql, filter_params = filter_builder.build_filter(filter)
                where_clause = f" WHERE {filter_sql}"
                parameters.extend(filter_params)
            elif isinstance(filter, str):
                where_clause = f" WHERE {filter}"

        # Build the vector similarity search query
        sql = f"""SELECT TOP @k c
FROM c{where_clause}
ORDER BY RANK VectorDistance(c{vector_path}, @vector)"""

        return sql, parameters

    def build_full_text_search(
        self,
        text: str,
        fields: list[str],
        k: int,
        filter: str | dict[str, Any] | None = None,
        filter_builder: Optional["FilterBuilder"] = None
    ) -> tuple[str, list[dict[str, Any]]]:
        """Build full-text search query using BM25.
        
        Returns:
            Tuple of (SQL query, parameters)
        """
        parameters = [
            {"name": "@k", "value": k},
            {"name": "@text", "value": text}
        ]

        # Build WHERE clause if filter provided
        where_clause = ""
        if filter:
            if isinstance(filter, dict) and filter_builder:
                filter_sql, filter_params = filter_builder.build_filter(filter)
                where_clause = f" WHERE {filter_sql}"
                parameters.extend(filter_params)
            elif isinstance(filter, str):
                where_clause = f" WHERE {filter}"

        # Build full-text score expression for multiple fields
        if len(fields) == 1:
            score_expr = f"FullTextScore(c{fields[0]}, @text)"
        else:
            # For multiple fields, we might need to combine scores
            # This is a simplified approach - actual implementation may vary
            field_scores = [f"FullTextScore(c{field}, @text)" for field in fields]
            score_expr = " + ".join(field_scores)

        sql = f"""SELECT TOP @k c
FROM c{where_clause}
ORDER BY RANK {score_expr}"""

        return sql, parameters

    def build_hybrid_search(
        self,
        text: str,
        vector: list[float],
        fields: list[str],
        vector_path: str,
        k: int,
        weights: list[int] | None = None,
        filter: str | dict[str, Any] | None = None,
        filter_builder: Optional["FilterBuilder"] = None
    ) -> tuple[str, list[dict[str, Any]]]:
        """Build hybrid search query using RRF (Reciprocal Rank Fusion).
        
        Returns:
            Tuple of (SQL query, parameters)
        """
        parameters = [
            {"name": "@k", "value": k},
            {"name": "@text", "value": text},
            {"name": "@vector", "value": vector}
        ]

        # Add weights if provided
        if weights:
            parameters.append({"name": "@weights", "value": weights})

        # Build WHERE clause if filter provided
        where_clause = ""
        if filter:
            if isinstance(filter, dict) and filter_builder:
                filter_sql, filter_params = filter_builder.build_filter(filter)
                where_clause = f" WHERE {filter_sql}"
                parameters.extend(filter_params)
            elif isinstance(filter, str):
                where_clause = f" WHERE {filter}"

        # Build full-text score expression
        if len(fields) == 1:
            ft_score_expr = f"FullTextScore(c{fields[0]}, @text)"
        else:
            field_scores = [f"FullTextScore(c{field}, @text)" for field in fields]
            ft_score_expr = " + ".join(field_scores)

        # Build vector distance expression
        vector_score_expr = f"VectorDistance(c{vector_path}, @vector)"

        # Build RRF expression
        if weights:
            rrf_expr = f"RRF({ft_score_expr}, {vector_score_expr}, @weights)"
        else:
            rrf_expr = f"RRF({ft_score_expr}, {vector_score_expr})"

        sql = f"""SELECT TOP @k c
FROM c{where_clause}
ORDER BY RANK {rrf_expr}"""

        return sql, parameters


class IndexManager:
    """Manages vector and full-text index provisioning."""

    async def ensure_indexes(
        self,
        container,  # AsyncContainerProxy
        database,  # AsyncDatabaseProxy
        container_name: str,
        settings: ContainerSettings
    ) -> dict[str, Any]:
        """Ensure vector and full-text indexes are provisioned.
        
        Returns:
            The effective indexing policy after updates
        """
        try:
            # Get current container properties
            container_props = await container.read()
            indexing_policy = container_props.get("indexingPolicy", {})

            # Track if we need to update the policy
            needs_update = False

            # Handle vector policy and indexes
            if settings.vector_policy or settings.vector_indexes:
                vector_policy, vector_indexes = self._build_vector_configuration(
                    settings.vector_policy or [],
                    settings.vector_indexes or []
                )

                # Update vector embedding policy
                if vector_policy:
                    if "vectorEmbeddingPolicy" not in container_props:
                        container_props["vectorEmbeddingPolicy"] = {"vectorEmbeddings": []}

                    current_embeddings = container_props["vectorEmbeddingPolicy"]["vectorEmbeddings"]

                    # Add new vector embeddings if not already present
                    for new_embedding in vector_policy["vectorEmbeddings"]:
                        if not any(
                            e.get("path") == new_embedding["path"]
                            for e in current_embeddings
                        ):
                            current_embeddings.append(new_embedding)
                            needs_update = True

                # Update vector indexes
                if vector_indexes:
                    if "vectorIndexes" not in indexing_policy:
                        indexing_policy["vectorIndexes"] = []

                    current_vector_indexes = indexing_policy["vectorIndexes"]

                    # Add new vector indexes if not already present
                    for new_index in vector_indexes:
                        if not any(
                            idx.get("path") == new_index["path"]
                            for idx in current_vector_indexes
                        ):
                            current_vector_indexes.append(new_index)
                            needs_update = True

            # Handle full-text indexes
            if settings.full_text_indexes:
                # Check if container already has full-text policy
                existing_full_text_policy = container_props.get("fullTextPolicy")
                
                if not existing_full_text_policy:
                    print("WARNING: Container does not have a full-text policy. Full-text indexes cannot be added after container creation.")
                    print("To use full-text search, recreate the container with full-text policy enabled.")
                else:
                    full_text_indexes = self._build_full_text_configuration(
                        settings.full_text_indexes
                    )

                    if "fullTextIndexes" not in indexing_policy:
                        indexing_policy["fullTextIndexes"] = []

                    current_ft_indexes = indexing_policy["fullTextIndexes"]

                    # Add new full-text indexes if not already present
                    for new_index in full_text_indexes:
                        if not any(
                            idx.get("path") == new_index["path"]
                            for idx in current_ft_indexes
                        ):
                            current_ft_indexes.append(new_index)
                            needs_update = True

            # Update container if needed
            if needs_update:
                # Build container specification for replacement
                # Note: replace_container needs partition_key as separate parameter
                partition_key_info = container_props.get("partitionKey", {})
                
                await database.replace_container(
                    container=container_name,
                    partition_key=partition_key_info,
                    indexing_policy=indexing_policy
                )

                # Re-read to get the effective policy
                container_props = await container.read()

            return container_props.get("indexingPolicy", {})

        except Exception as ex:
            raise CosmosODMError(f"Failed to ensure indexes: {str(ex)}") from ex

    def _build_vector_configuration(
        self,
        vector_policy_specs: list[VectorPolicySpec],
        vector_index_specs: list[VectorIndexSpec]
    ) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
        """Build vector policy and index configuration."""
        vector_policy = None
        vector_indexes = []

        if vector_policy_specs:
            vector_embeddings = []
            for spec in vector_policy_specs:
                embedding = {
                    "path": spec.path,
                    "dataType": spec.data_type,
                    "dimensions": spec.dimensions,
                    "distanceFunction": spec.distance_function
                }
                vector_embeddings.append(embedding)

            vector_policy = {"vectorEmbeddings": vector_embeddings}

        if vector_index_specs:
            for spec in vector_index_specs:
                index = {
                    "path": spec.path,
                    "type": spec.type
                }
                vector_indexes.append(index)

        return vector_policy, vector_indexes

    def _build_full_text_configuration(
        self,
        full_text_specs: list[FullTextIndexSpec]
    ) -> list[dict[str, Any]]:
        """Build full-text index configuration."""
        indexes = []

        for spec in full_text_specs:
            # Create separate index entries for each path
            for path in spec.paths:
                index = {"path": path}
                indexes.append(index)

        return indexes

    def validate_vector_search_support(
        self,
        indexing_policy: dict[str, Any],
        vector_path: str
    ) -> None:
        """Validate that vector search is supported for the given path."""
        vector_indexes = indexing_policy.get("vectorIndexes", [])

        if not any(idx.get("path") == vector_path for idx in vector_indexes):
            raise VectorIndexMissing(
                f"No vector index found for path '{vector_path}'",
                vector_path=vector_path
            )

    def validate_full_text_search_support(
        self,
        indexing_policy: dict[str, Any],
        text_paths: list[str]
    ) -> None:
        """Validate that full-text search is supported for the given paths."""
        full_text_indexes = indexing_policy.get("fullTextIndexes", [])

        # Check if any full-text index covers the requested paths
        for path in text_paths:
            covered = False
            for ft_index in full_text_indexes:
                if path in ft_index.get("paths", []):
                    covered = True
                    break

            if not covered:
                raise FullTextIndexMissing(
                    f"No full-text index found covering path '{path}'",
                    text_paths=text_paths
                )
