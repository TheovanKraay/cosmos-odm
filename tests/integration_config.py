"""Integration test configuration and utilities."""

import os
import asyncio
from typing import Dict, Any


# Cosmos DB Local Emulator Settings
EMULATOR_CONFIG = {
    "endpoint": "https://localhost:8081",
    "key": "C2y6yDjf5/R+ob0N8A7Cgv30VRDJIWEHLM+4QDU5DE2nQ9nDuVTqobD4b8mGGyPMbIZnqyMsEcaGQy67XIw/Jw==",
    "database": "TestODMIntegration"
}


def check_emulator_available() -> bool:
    """Check if Cosmos DB emulator is running."""
    import requests
    try:
        response = requests.get(
            EMULATOR_CONFIG["endpoint"],
            verify=False,  # Emulator uses self-signed cert
            timeout=5
        )
        return response.status_code in [200, 401]  # 401 is normal for auth endpoint
    except:
        return False


async def cleanup_test_database(client_manager):
    """Clean up test database after tests."""
    try:
        async_client = await client_manager.get_async_client()
        await async_client.delete_database(EMULATOR_CONFIG["database"])
    except:
        pass  # Database might not exist


class IntegrationTestBase:
    """Base class for integration tests with common utilities."""
    
    @staticmethod
    def create_test_connection_string() -> str:
        """Create connection string for local emulator."""
        return f"AccountEndpoint={EMULATOR_CONFIG['endpoint']};AccountKey={EMULATOR_CONFIG['key']};DisableSSLVerification=true"
    
    @staticmethod
    def get_test_database_name() -> str:
        """Get test database name."""
        return EMULATOR_CONFIG["database"]
    
    @staticmethod
    async def wait_for_container_ready(collection, max_retries: int = 10):
        """Wait for container to be ready for operations."""
        for i in range(max_retries):
            try:
                # Try a simple operation to verify container is ready
                await collection._get_container()
                return True
            except Exception as e:
                if i == max_retries - 1:
                    raise e
                await asyncio.sleep(1)
        return False