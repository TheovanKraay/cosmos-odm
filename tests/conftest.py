"""Test configuration and fixtures for Cosmos ODM.

This module provides environment-aware test configuration that can switch between:
- Local Cosmos DB Emulator (default)
- Azure Cosmos DB Cloud (when AZURE_COSMOSDB_ENDPOINT is set)
"""

import os
import pytest
from typing import Dict, Any


class TestConfig:
    """Configuration for test environments."""
    
    def __init__(self):
        self.azure_endpoint = os.getenv("AZURE_COSMOSDB_ENDPOINT")
        self.is_cloud = bool(self.azure_endpoint)
        
    @property
    def endpoint(self) -> str:
        """Get the appropriate Cosmos DB endpoint."""
        if self.is_cloud:
            return self.azure_endpoint
        else:
            # Local emulator endpoint - MUST use 127.0.0.1, NOT localhost
            # On Windows, localhost resolves to ::1 (IPv6) but emulator binds IPv4 only
            return "https://127.0.0.1:8081"
    
    @property
    def key(self) -> str:
        """Get the appropriate Cosmos DB key."""
        if self.is_cloud:
            # For cloud, use Default Azure Credentials (no key needed)
            return None
        else:
            # Local emulator key (well-known default)
            return "C2y6yDjf5/R+ob0N8A7Cgv30VRDJIWEHLM+4QDU5DE2nQ9nDuVTqobD4b8mGGyPMbIZnqyMsEcaGQy67XIw/Jw=="
    
    @property
    def database_name(self) -> str:
        """Get the appropriate database name for the environment."""
        if self.is_cloud:
            # Pre-existing database name for cloud testing
            return "cosmos-odm-db"
        else:
            # Dynamic database name for emulator
            return "TestDatabase"
    
    @property
    def supports_vector_search(self) -> bool:
        """Check if the current environment supports vector search."""
        return self.is_cloud
    
    @property
    def supports_full_text_search(self) -> bool:
        """Check if the current environment supports full-text search."""
        return self.is_cloud
    
    @property
    def supports_hybrid_search(self) -> bool:
        """Check if the current environment supports hybrid search."""
        return self.is_cloud
    
    @property
    def supports_index_management(self) -> bool:
        """Check if the current environment supports index management."""
        return self.is_cloud
    
    def get_skip_reason(self, feature: str) -> str:
        """Get skip reason for unsupported features."""
        if self.is_cloud:
            return None
        return f"{feature} not supported in Cosmos DB Local Emulator"


# Global test configuration instance
test_config = TestConfig()


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "requires_cloud: mark test as requiring Azure Cosmos DB cloud features"
    )
    config.addinivalue_line(
        "markers", "emulator_only: mark test as only working with local emulator"
    )


def pytest_runtest_setup(item):
    """Skip tests based on environment capabilities."""
    # Skip cloud-only tests when using emulator
    if item.get_closest_marker("requires_cloud") and not test_config.is_cloud:
        pytest.skip("Test requires Azure Cosmos DB cloud features")
    
    # Skip emulator-only tests when using cloud
    if item.get_closest_marker("emulator_only") and test_config.is_cloud:
        pytest.skip("Test only works with local emulator")


@pytest.fixture(scope="session")
def cosmos_config():
    """Provide test configuration for the session."""
    return test_config


@pytest.fixture(scope="session") 
def environment_info():
    """Provide environment information for tests."""
    return {
        "is_cloud": test_config.is_cloud,
        "endpoint": test_config.endpoint,
        "supports_vector_search": test_config.supports_vector_search,
        "supports_full_text_search": test_config.supports_full_text_search,
        "supports_hybrid_search": test_config.supports_hybrid_search,
        "supports_index_management": test_config.supports_index_management,
    }