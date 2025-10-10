import asyncio
import uuid
from cosmos_odm import CosmosClientManager
from pydantic import Field
from cosmos_odm import Document, container, PK, ETag
from typing import List

@container(
    name="documents",
    partition_key_path="/tenantId",
    ttl=30*24*3600,  # 30 days TTL
    full_text_indexes=[{
        "paths": ["/title", "/content"]
    }]
)
class MyDocument(Document):
    id: str
    tenantId: PK[str] = Field(serialization_alias="tenantId")
    title: str
    content: str
    content_vector: List[float] | None = None
    status: str = "draft"
    etag: ETag | None = None

async def main():
    try:
        # Authentication Options:
        
        # Option 1: Connection string (simplest for development)
        # client_manager = CosmosClientManager(
        #     connection_string="AccountEndpoint=https://your-account.documents.azure.com:443/;AccountKey=your-key==;"
        # )
        
        # Option 2: Account key  
        # client_manager = CosmosClientManager(
        #     endpoint="https://your-account.documents.azure.com:443/",
        #     key="your-account-key-here"
        # )
        
        # Option 3: DefaultAzureCredential (recommended for production)
        # Automatically uses Azure CLI, Managed Identity, Service Principal, etc.
        # Make sure you're authenticated with Azure CLI: az login
        client_manager = CosmosClientManager(
           endpoint="https://tvk-my-cosmos-account.documents.azure.com:443/",
           key=None  # Explicitly set to None to use DefaultAzureCredential
        )
        
        # Bind to collection
        docs = await MyDocument.bind(
            database="my-odm-app-db",
            client_manager=client_manager
        )
        
        # Ensure indexes are provisioned (vector and full-text indexes)
        print("Ensuring indexes...")
        await docs.ensure_indexes()
        print("Indexes ensured successfully!")
        
        # Create document with a unique ID to avoid conflicts
        doc = MyDocument(
            id=f"doc-{uuid.uuid4()}",
            tenantId=PK("tenant-1"),
            title="Introduction to Vector Search",
            content="Vector search enables semantic similarity...",
            content_vector=[0.1, 0.2, 0.3, 0.4, 0.5]  # Example 5-dimensional vector
        )
        
        # Create the document
        created_doc = await docs.create(doc)
        print(f"Created document: {created_doc.id}")
        
        # Check if RU metrics are available
        if hasattr(created_doc, '_ru_metrics') and created_doc._ru_metrics:
            print(f"Request charge: {created_doc._ru_metrics.request_charge} RU")
        else:
            print("RU metrics not available")
        
        # Point read (most efficient)
        doc_read = await docs.get(pk="tenant-1", id=created_doc.id)
        print(f"Read document: {doc_read.title}")
        
        # Update document with ETag-based optimistic concurrency
        doc_read.status = "published"
        if doc_read.etag and doc_read.etag.value:
            updated_doc = await docs.replace(doc_read, if_match=doc_read.etag.value)
        else:
            updated_doc = await docs.replace(doc_read)
        print(f"Updated document status to: {updated_doc.status}")
        
        # Clean up - delete the document
        await docs.delete(pk="tenant-1", id=created_doc.id)
        print("Document deleted successfully!")
        print("Test completed successfully!")
        
    except Exception as e:
        print(f"Error: {e}")
        print("\nAuthentication troubleshooting:")
        print("1. For Azure CLI: Run 'az login' first")
        print("2. For Service Principal: Set AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID")
        print("3. For Managed Identity: Ensure your resource has the identity assigned")
        print("4. Alternatively, use connection string or key-based authentication")
        print("5. For DefaultAzureCredential: Explicitly set key=None to avoid environment variable conflicts")

if __name__ == "__main__":
    asyncio.run(main())