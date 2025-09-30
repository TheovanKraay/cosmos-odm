"""Filter builders for converting dict filters to Cosmos SQL WHERE clauses."""

from typing import Any


class FilterBuilder:
    """Converts dictionary filters to Cosmos SQL WHERE clauses."""

    def build_filter(self, filter_dict: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
        """Convert a filter dictionary to SQL WHERE clause and parameters.
        
        Args:
            filter_dict: Dictionary with field filters like {"status": "active", "age": {"$gt": 18}}
            
        Returns:
            Tuple of (WHERE clause SQL, parameters list)
        """
        conditions = []
        parameters = []
        param_counter = 0

        for field, value in filter_dict.items():
            condition, field_params, param_counter = self._build_field_condition(
                field, value, param_counter
            )
            conditions.append(condition)
            parameters.extend(field_params)

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        return where_clause, parameters

    def _build_field_condition(
        self,
        field: str,
        value: Any,
        param_counter: int
    ) -> tuple[str, list[dict[str, Any]], int]:
        """Build condition for a single field."""
        field_path = f"c.{field}" if not field.startswith("/") else f"c{field}"

        if isinstance(value, dict):
            # Handle operator-based conditions like {"$gt": 18, "$lt": 65}
            return self._build_operator_conditions(field_path, value, param_counter)
        else:
            # Handle simple equality
            param_name = f"@param{param_counter}"
            param_counter += 1

            condition = f"{field_path} = {param_name}"
            parameters = [{"name": param_name, "value": value}]

            return condition, parameters, param_counter

    def _build_operator_conditions(
        self,
        field_path: str,
        operators: dict[str, Any],
        param_counter: int
    ) -> tuple[str, list[dict[str, Any]], int]:
        """Build conditions for operator-based filters."""
        conditions = []
        parameters = []

        for operator, value in operators.items():
            old_param_counter = param_counter
            condition, param_counter = self._build_single_operator_condition(
                field_path, operator, value, param_counter
            )

            if condition:
                conditions.append(condition)

                # Only add parameters if param_counter was incremented
                if param_counter > old_param_counter:
                    if isinstance(value, (list, tuple)):
                        # For $in operator
                        parameters.extend([
                            {"name": f"@param{param_counter - len(value) + i}", "value": v}
                            for i, v in enumerate(value)
                        ])
                    else:
                        param_name = f"@param{param_counter - 1}"
                        parameters.append({"name": param_name, "value": value})

        combined_condition = " AND ".join(conditions) if conditions else "1=1"
        return combined_condition, parameters, param_counter

    def _build_single_operator_condition(
        self,
        field_path: str,
        operator: str,
        value: Any,
        param_counter: int
    ) -> tuple[str, int]:
        """Build condition for a single operator."""
        param_name = f"@param{param_counter}"

        if operator == "$eq":
            condition = f"{field_path} = {param_name}"
            param_counter += 1
        elif operator == "$ne":
            condition = f"{field_path} != {param_name}"
            param_counter += 1
        elif operator == "$gt":
            condition = f"{field_path} > {param_name}"
            param_counter += 1
        elif operator == "$gte":
            condition = f"{field_path} >= {param_name}"
            param_counter += 1
        elif operator == "$lt":
            condition = f"{field_path} < {param_name}"
            param_counter += 1
        elif operator == "$lte":
            condition = f"{field_path} <= {param_name}"
            param_counter += 1
        elif operator == "$in":
            if isinstance(value, (list, tuple)) and value:
                param_names = []
                for _ in value:
                    param_names.append(f"@param{param_counter}")
                    param_counter += 1
                condition = f"{field_path} IN ({', '.join(param_names)})"
            else:
                condition = "1=0"  # No values to match
        elif operator == "$nin":
            if isinstance(value, (list, tuple)) and value:
                param_names = []
                for _ in value:
                    param_names.append(f"@param{param_counter}")
                    param_counter += 1
                condition = f"{field_path} NOT IN ({', '.join(param_names)})"
            else:
                condition = "1=1"  # All values match
        elif operator == "$exists":
            condition = f"IS_DEFINED({field_path})" if value else f"NOT IS_DEFINED({field_path})"
            # Don't increment param_counter for $exists as it doesn't use parameters
        elif operator == "$regex":
            # Cosmos DB uses CONTAINS, STARTSWITH, ENDSWITH for string matching
            # This is a simplified implementation
            condition = f"CONTAINS({field_path}, {param_name})"
            param_counter += 1
        elif operator == "$contains":
            condition = f"CONTAINS({field_path}, {param_name})"
            param_counter += 1
        elif operator == "$startswith":
            condition = f"STARTSWITH({field_path}, {param_name})"
            param_counter += 1
        elif operator == "$endswith":
            condition = f"ENDSWITH({field_path}, {param_name})"
            param_counter += 1
        else:
            raise ValueError(f"Unsupported operator: {operator}")

        return condition, param_counter
