"""Real-world example: Document management system with vector search.

This example demonstrates a more complex, realistic use case:
- Document storage with metadata
- Content embeddings for semantic search  
- File attachment handling
- Version control and audit trails
- Full-text and semantic search
"""

import asyncio
import hashlib
from datetime import datetime
from typing import List, Optional
from enum import Enum

from cosmos_odm import Document, container, PK
from cosmos_odm.client import CosmosClientManager
from cosmos_odm.types import VectorPolicySpec, VectorIndexSpec, FullTextIndexSpec


class DocumentType(str, Enum):
    """Document type enumeration."""
    POLICY = "policy"
    PROCEDURE = "procedure"
    HANDBOOK = "handbook"
    MEMO = "memo"
    REPORT = "report"


class DocumentStatus(str, Enum):
    """Document status enumeration."""
    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    ARCHIVED = "archived"


@container(
    name="documents",
    partition_key_path="/tenant_id",
    vector_policy=[VectorPolicySpec(path="/content_embedding", data_type="float32", dimensions=384)],
    vector_indexes=[VectorIndexSpec(path="/content_embedding", type="flat")],
    full_text_indexes=[FullTextIndexSpec(paths=["/title", "/content", "/tags", "/author"])]
)
class CompanyDocument(Document):
    """Company document with semantic search capabilities."""
    
    # Partition key
    tenant_id: PK[str]
    
    # Document metadata
    title: str
    content: str
    document_type: DocumentType
    status: DocumentStatus
    author: str
    department: str
    
    # Search and classification
    content_embedding: List[float]
    tags: List[str] = []
    keywords: List[str] = []
    
    # Versioning and audit
    version: int = 1
    previous_version_id: Optional[str] = None
    created_by: str
    last_modified_by: str
    
    # Access control
    access_level: str = "internal"  # public, internal, confidential, restricted
    allowed_departments: List[str] = []
    
    # Metrics
    view_count: int = 0
    download_count: int = 0
    last_accessed: Optional[datetime] = None


@container(
    name="document_versions",
    partition_key_path="/document_id"
)
class DocumentVersion(Document):
    """Document version history."""
    document_id: PK[str]
    version_number: int
    content_snapshot: str
    changed_by: str
    change_summary: str
    change_timestamp: datetime


class DocumentManager:
    """Document management system using Cosmos ODM."""
    
    def __init__(self, client_manager: CosmosClientManager, tenant_id: str):
        self.client_manager = client_manager
        self.tenant_id = tenant_id
        self.documents_collection = None
        self.versions_collection = None
    
    async def initialize(self):
        """Initialize collections."""
        self.documents_collection = await CompanyDocument.bind(
            "DocumentManagement", 
            client_manager=self.client_manager
        )
        self.versions_collection = await DocumentVersion.bind(
            "DocumentManagement",
            client_manager=self.client_manager
        )
    
    async def create_document(
        self,
        title: str,
        content: str,
        document_type: DocumentType,
        author: str,
        department: str,
        tags: List[str] = None,
        access_level: str = "internal"
    ) -> CompanyDocument:
        """Create a new document with embedding."""
        
        # Generate content embedding (mock)
        embedding = await self._generate_embedding(content)
        
        # Extract keywords (simplified)
        keywords = self._extract_keywords(content)
        
        document = CompanyDocument(
            tenant_id=PK(self.tenant_id),
            title=title,
            content=content,
            document_type=document_type,
            status=DocumentStatus.DRAFT,
            author=author,
            department=department,
            content_embedding=embedding,
            tags=tags or [],
            keywords=keywords,
            created_by=author,
            last_modified_by=author,
            access_level=access_level
        )
        
        created = await self.documents_collection.create(document)
        
        # Create initial version
        await self._create_version(
            document_id=created.id,
            version_number=1,
            content=content,
            changed_by=author,
            change_summary="Initial document creation"
        )
        
        return created
    
    async def update_document(
        self,
        document_id: str,
        new_content: str,
        modified_by: str,
        change_summary: str = "Document updated"
    ) -> CompanyDocument:
        """Update document content and create new version."""
        
        # Get current document
        document = await self.documents_collection.get(document_id, PK(self.tenant_id))
        
        # Update content and embedding
        document.content = new_content
        document.content_embedding = await self._generate_embedding(new_content)
        document.keywords = self._extract_keywords(new_content)
        document.version += 1
        document.last_modified_by = modified_by
        
        # Save updated document
        updated = await self.documents_collection.replace(document)
        
        # Create version history
        await self._create_version(
            document_id=document_id,
            version_number=updated.version,
            content=new_content,
            changed_by=modified_by,
            change_summary=change_summary
        )
        
        return updated
    
    async def search_documents_semantic(
        self,
        query: str,
        limit: int = 10,
        department_filter: str = None,
        document_type_filter: DocumentType = None
    ) -> List[CompanyDocument]:
        """Search documents using semantic similarity."""
        
        # Generate query embedding
        query_embedding = await self._generate_embedding(query)
        
        # Build filter
        filter_dict = {"tenant_id": self.tenant_id}
        if department_filter:
            filter_dict["department"] = department_filter
        if document_type_filter:
            filter_dict["document_type"] = document_type_filter.value
        
        try:
            results = await self.documents_collection.vector_search(
                vector_field="content_embedding",
                query_vector=query_embedding,
                limit=limit,
                filter=filter_dict
            )
            return results.items
        except Exception:
            # Fallback to text search if vector search not available
            return await self.search_documents_text(query, limit, department_filter, document_type_filter)
    
    async def search_documents_text(
        self,
        query: str,
        limit: int = 10,
        department_filter: str = None,
        document_type_filter: DocumentType = None
    ) -> List[CompanyDocument]:
        """Search documents using full-text search."""
        
        # Build filter
        filter_dict = {"tenant_id": self.tenant_id}
        if department_filter:
            filter_dict["department"] = department_filter
        if document_type_filter:
            filter_dict["document_type"] = document_type_filter.value
        
        try:
            results = await self.documents_collection.full_text_search(
                text_fields=["title", "content", "tags"],
                query_text=query,
                limit=limit,
                filter=filter_dict
            )
            return results.items
        except Exception:
            # Fallback to basic query
            return await self._search_documents_basic(query, limit, filter_dict)
    
    async def get_document_versions(self, document_id: str) -> List[DocumentVersion]:
        """Get all versions of a document."""
        versions = []
        async for page in self.versions_collection.query(
            "SELECT * FROM c WHERE c.document_id = @doc_id ORDER BY c.version_number DESC",
            parameters={"doc_id": document_id}
        ):
            versions.extend(page.items)
        return versions
    
    async def get_documents_by_department(self, department: str) -> List[CompanyDocument]:
        """Get all documents for a department."""
        documents = []
        async for page in self.documents_collection.query(
            "SELECT * FROM c",
            filter={"tenant_id": self.tenant_id, "department": department}
        ):
            documents.extend(page.items)
        return documents
    
    async def get_document_analytics(self) -> dict:
        """Get document analytics for the tenant."""
        # Count by type
        type_counts = {}
        status_counts = {}
        department_counts = {}
        
        async for page in self.documents_collection.query(
            "SELECT * FROM c",
            filter={"tenant_id": self.tenant_id}
        ):
            for doc in page.items:
                # Count by type
                doc_type = doc.document_type
                type_counts[doc_type] = type_counts.get(doc_type, 0) + 1
                
                # Count by status
                status = doc.status
                status_counts[status] = status_counts.get(status, 0) + 1
                
                # Count by department
                dept = doc.department
                department_counts[dept] = department_counts.get(dept, 0) + 1
        
        return {
            "by_type": type_counts,
            "by_status": status_counts,
            "by_department": department_counts
        }
    
    async def _create_version(
        self,
        document_id: str,
        version_number: int,
        content: str,
        changed_by: str,
        change_summary: str
    ):
        """Create document version entry."""
        version = DocumentVersion(
            document_id=PK(document_id),
            version_number=version_number,
            content_snapshot=content,
            changed_by=changed_by,
            change_summary=change_summary,
            change_timestamp=datetime.utcnow()
        )
        await self.versions_collection.create(version)
    
    async def _generate_embedding(self, text: str) -> List[float]:
        """Generate mock embedding for text."""
        # In production, use real embedding service
        hash_obj = hashlib.md5(text.encode())
        hash_int = int(hash_obj.hexdigest(), 16)
        
        embedding = []
        for i in range(384):
            value = ((hash_int + i) % 10000) / 5000.0 - 1.0
            embedding.append(value)
        
        return embedding
    
    def _extract_keywords(self, content: str) -> List[str]:
        """Extract keywords from content (simplified)."""
        # In production, use proper NLP library
        words = content.lower().split()
        keywords = [w for w in words if len(w) > 4 and w.isalpha()]
        return list(set(keywords))[:10]  # Top 10 unique keywords
    
    async def _search_documents_basic(self, query: str, limit: int, filter_dict: dict) -> List[CompanyDocument]:
        """Basic search fallback."""
        documents = []
        query_lower = query.lower()
        
        async for page in self.documents_collection.query(
            "SELECT * FROM c",
            filter=filter_dict,
            max_item_count=limit * 2  # Get more to filter
        ):
            for doc in page.items:
                # Simple text matching
                if (query_lower in doc.title.lower() or 
                    query_lower in doc.content.lower() or
                    any(query_lower in tag.lower() for tag in doc.tags)):
                    documents.append(doc)
                    if len(documents) >= limit:
                        break
            if len(documents) >= limit:
                break
        
        return documents[:limit]


async def demo_document_management():
    """Demonstrate the document management system."""
    print("📁 Document Management System Demo")
    
    # Initialize
    client_manager = CosmosClientManager(
        endpoint="https://localhost:8081",
        key="C2y6yDjf5/R+ob0N8A7Cgv30VRDJIWEHLM+4QDU5DE2nQ9nDuVTqobD4b8mGGyPMbIZnqyMsEcaGQy67XIw/Jw=="
    )
    
    doc_manager = DocumentManager(client_manager, "company_abc")
    await doc_manager.initialize()
    
    try:
        # Create sample documents
        print("\n📝 Creating sample documents...")
        
        policy_doc = await doc_manager.create_document(
            title="Remote Work Policy",
            content="This policy outlines the guidelines for remote work arrangements. Employees must maintain productivity standards while working from home. Communication tools such as Slack and Teams should be used for coordination. Regular check-ins with managers are required.",
            document_type=DocumentType.POLICY,
            author="HR Team",
            department="Human Resources",
            tags=["remote work", "policy", "productivity"],
            access_level="internal"
        )
        
        handbook_doc = await doc_manager.create_document(
            title="Employee Handbook 2024",
            content="Welcome to our company! This handbook contains important information about company culture, benefits, policies, and procedures. Please read this carefully and keep it as a reference. It covers topics like vacation time, health insurance, code of conduct, and professional development opportunities.",
            document_type=DocumentType.HANDBOOK,
            author="HR Team", 
            department="Human Resources",
            tags=["handbook", "benefits", "culture", "onboarding"]
        )
        
        tech_doc = await doc_manager.create_document(
            title="API Documentation Guidelines",
            content="This document describes best practices for writing API documentation. Include clear examples, parameter descriptions, error codes, and authentication requirements. Use consistent formatting and provide code samples in multiple programming languages.",
            document_type=DocumentType.PROCEDURE,
            author="Tech Lead",
            department="Engineering",
            tags=["API", "documentation", "development", "standards"]
        )
        
        print(f"✅ Created documents: {policy_doc.title}, {handbook_doc.title}, {tech_doc.title}")
        
        # Update a document
        print("\n✏️ Updating document...")
        updated_policy = await doc_manager.update_document(
            document_id=policy_doc.id,
            new_content=policy_doc.content + " Additionally, all remote workers must attend weekly team meetings via video conference.",
            modified_by="Manager",
            change_summary="Added weekly meeting requirement"
        )
        print(f"✅ Updated document version: {updated_policy.version}")
        
        # Search documents
        print("\n🔍 Searching documents...")
        
        # Semantic search
        semantic_results = await doc_manager.search_documents_semantic("remote work guidelines")
        print(f"📊 Semantic search found {len(semantic_results)} documents")
        for doc in semantic_results:
            print(f"  • {doc.title} ({doc.document_type})")
        
        # Text search
        text_results = await doc_manager.search_documents_text("API development")
        print(f"📝 Text search found {len(text_results)} documents")
        for doc in text_results:
            print(f"  • {doc.title} ({doc.department})")
        
        # Department filter
        hr_docs = await doc_manager.get_documents_by_department("Human Resources")
        print(f"🏢 HR department has {len(hr_docs)} documents")
        
        # Version history
        versions = await doc_manager.get_document_versions(policy_doc.id)
        print(f"📚 Policy document has {len(versions)} versions")
        for version in versions:
            print(f"  v{version.version_number}: {version.change_summary} by {version.changed_by}")
        
        # Analytics
        analytics = await doc_manager.get_document_analytics()
        print("\n📈 Document Analytics:")
        print(f"  By Type: {analytics['by_type']}")
        print(f"  By Status: {analytics['by_status']}")
        print(f"  By Department: {analytics['by_department']}")
        
        print("\n🎉 Document management demo completed!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await client_manager.close()


if __name__ == "__main__":
    asyncio.run(demo_document_management())