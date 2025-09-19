import chromadb
from chromadb.config import Settings
from openai import OpenAI
import os
from typing import Dict, List, Any, Optional
import json
import logging
from database import (
    get_schema_info,
    get_table_relationships,
    get_schema_info_with_overrides,
    get_table_relationships_with_overrides,
)
from config import VECTOR_DB_CONFIG, LLM_CONFIG
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction

# Configure logging
logger = logging.getLogger(__name__)

class SchemaVectorizer:
    """
    Handles schema extraction, vectorization, and similarity search
    """
    
    def __init__(self):
        self.client = None
        self.collection = None
        self.model = None
        self.embedding_function = None
        self.schema_cache = {}
        self._overrides: Optional[Dict[str, Any]] = None
        self._username: Optional[str] = None
        
    def initialize(self):
        """Initialize the vector database and embedding model"""
        try:
            # Initialize ChromaDB client
            self.client = chromadb.PersistentClient(
                path=VECTOR_DB_CONFIG['persist_directory'],
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            
            # Prepare OpenAI client for cloud embeddings (supports OpenAI-compatible endpoints)
            api_key = LLM_CONFIG.get('openai_api_key', '')
            base_url = LLM_CONFIG.get('base_url') or None
            if not api_key:
                raise ValueError("OPENAI_API_KEY is required for cloud embeddings")

            # Use Chroma built-in embedding function for compatibility
            model_name = VECTOR_DB_CONFIG.get('embedding_model', 'text-embedding-v4')
            self.embedding_function = OpenAIEmbeddingFunction(
                api_key=api_key,
                api_base=base_url or None,
                model_name=model_name,
            )

            self.collection = self.client.get_or_create_collection(
                name=VECTOR_DB_CONFIG['collection_name'],
                embedding_function=self.embedding_function,
            )
            
            logger.info("SchemaVectorizer initialized successfully")
            
            # Load schema if collection is empty
            if self.collection.count() == 0:
                self.refresh_schema()
                
        except Exception as e:
            logger.error(f"Failed to initialize SchemaVectorizer: {str(e)}")
            raise

    def initialize_with_user_config(self, user_cfg: Dict[str, Any], username: str):
        """Initialize the vector DB and embedding model using per-user embedding config.

        user_cfg expects an 'embedding' node containing base_url, model, api_key.
        """
        try:
            # Initialize ChromaDB client (shared persistent store)
            self.client = chromadb.PersistentClient(
                path=VECTOR_DB_CONFIG['persist_directory'],
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )

            emb = (user_cfg or {}).get('embedding', {})
            api_key = emb.get('api_key')
            base_url = emb.get('base_url') or None
            model_name = emb.get('model') or VECTOR_DB_CONFIG.get('embedding_model', 'text-embedding-v4')
            if not api_key:
                raise ValueError("Per-user embedding config missing 'api_key'")
            # Use Chroma built-in embedding function for compatibility (per-user)
            self.embedding_function = OpenAIEmbeddingFunction(
                api_key=api_key,
                api_base=base_url or None,
                model_name=model_name,
            )

            # Per-user collection name
            base_collection = VECTOR_DB_CONFIG['collection_name']
            collection_name = f"{base_collection}__{username}"
            self.collection = self.client.get_or_create_collection(
                name=collection_name,
                embedding_function=self.embedding_function,
            )

            # Store MySQL overrides for later refresh/search
            mysql_cfg = (user_cfg or {}).get('mysql', {})
            self._overrides = {
                k: mysql_cfg.get(k)
                for k in ("host", "port", "user", "password", "database", "charset")
                if mysql_cfg.get(k) is not None
            }
            self._username = username

            logger.info(f"SchemaVectorizer initialized successfully (per-user config, collection={collection_name})")
        except Exception as e:
            logger.error(f"Failed to initialize SchemaVectorizer with user config: {str(e)}")
            raise

    def refresh_schema(self):
        """Refresh schema information from the database"""
        try:
            logger.info("Refreshing database schema...")
            logger.info(f"get_schema_info_with_overrides.self: {self}")
            
            # Get schema information with overrides if present
            if self._overrides:
                schema_result = get_schema_info_with_overrides(self._overrides)
            else:
                schema_result = get_schema_info()
            if not schema_result["success"]:
                raise Exception(f"Failed to get schema info: {schema_result['error']}")
            
            # Get table relationships
            if self._overrides:
                relationships_result = get_table_relationships_with_overrides(self._overrides)
            else:
                relationships_result = get_table_relationships()
            relationships = {}
            if relationships_result["success"]:
                for rel in relationships_result["data"]:
                    table = rel["TABLE_NAME"]
                    if table not in relationships:
                        relationships[table] = []
                    relationships[table].append(rel)
            
            # Clear existing collection and recreate with embedding function
            current_name = self.collection.name if self.collection else VECTOR_DB_CONFIG['collection_name']
            self.client.delete_collection(current_name)
            self.collection = self.client.create_collection(
                name=current_name,
                embedding_function=self.embedding_function,
            )
            
            # Process each table
            documents = []
            metadatas = []
            ids = []
            
            for table_name, table_info in schema_result["data"].items():
                # Create comprehensive schema description
                schema_text = self._create_schema_description(
                    table_name, table_info, relationships.get(table_name, [])
                )
                
                documents.append(schema_text)
                metadatas.append({
                    "table_name": table_name,
                    "type": "table_schema"
                })
                ids.append(f"table_{table_name}")
                
                logger.info(f"Processed table: {table_name}")
            
            # Add to vector database
            #todo 想办法取最新的documents
            if documents:
                self.collection.add(
                    documents=documents,
                    metadatas=metadatas,
                    ids=ids
                )
                logger.info(f"Added {len(documents)} table schemas to vector database")
            
            self.schema_cache = schema_result["data"]
            
        except Exception as e:
            logger.error(f"Failed to refresh schema: {str(e)}")
            raise

    def _create_schema_description(self, table_name: str, table_info: Dict, relationships: List) -> str:
        """Create a comprehensive text description of a table schema"""
        
        description_parts = []
        
        # Table header
        description_parts.append(f"Table: {table_name}")
        description_parts.append("=" * 50)
        
        # CREATE TABLE statement
        if table_info.get("create_statement"):
            description_parts.append("DDL Statement:")
            description_parts.append(table_info["create_statement"])
            description_parts.append("")
        
        # Column descriptions
        description_parts.append("Columns:")
        for column in table_info["columns"]:
            col_name = column["Field"]
            col_type = column["Type"]
            col_null = column["Null"]
            col_key = column["Key"]
            col_default = column["Default"]
            col_extra = column["Extra"]
            
            col_desc = f"  - {col_name}: {col_type}"
            if col_null == "NO":
                col_desc += " NOT NULL"
            if col_key:
                col_desc += f" {col_key.upper()}"
            if col_default is not None:
                col_desc += f" DEFAULT {col_default}"
            if col_extra:
                col_desc += f" {col_extra}"
            
            description_parts.append(col_desc)
        
        # Relationships
        if relationships:
            description_parts.append("")
            description_parts.append("Foreign Key Relationships:")
            for rel in relationships:
                description_parts.append(
                    f"  - {rel['COLUMN_NAME']} -> {rel['REFERENCED_TABLE_NAME']}.{rel['REFERENCED_COLUMN_NAME']}"
                )
        
        # Add table purpose description (you can enhance this)
        description_parts.append("")
        description_parts.append("Purpose:")
        description_parts.append(f"This table stores {table_name.replace('_', ' ')} information.")
        
        return "\n".join(description_parts)

    def search_relevant_schema(self, query: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """
        Search for relevant schema information based on the query
        
        Args:
            query: User's natural language query
            n_results: Number of relevant schemas to return
            
        Returns:
            List of relevant schema information
        """
        try:
            # Search in the vector database
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results
            )
            
            relevant_schemas = []
            if results["documents"] and results["documents"][0]:
                for i, (doc, metadata) in enumerate(zip(results["documents"][0], results["metadatas"][0])):
                    relevant_schemas.append({
                        "schema_text": doc,
                        "table_name": metadata["table_name"],
                        "relevance_score": results["distances"][0][i] if results["distances"] else 0
                    })
            
            return relevant_schemas
            
        except Exception as e:
            logger.error(f"Failed to search relevant schema: {str(e)}")
            return []

    def get_table_schema(self, table_name: str) -> Optional[Dict[str, Any]]:
        """Get schema information for a specific table"""
        return self.schema_cache.get(table_name)

    def get_all_schemas(self) -> Dict[str, Any]:
        """Get all cached schema information"""
        return self.schema_cache

# Example usage for testing
if __name__ == "__main__":
    vectorizer = SchemaVectorizer()
    vectorizer.initialize()
    
    # Test search
    results = vectorizer.search_relevant_schema("find customer information")
    for result in results:
        print(f"Table: {result['table_name']}")
        print(f"Relevance: {result['relevance_score']}")
        print(f"Schema: {result['schema_text'][:200]}...")
        print("-" * 50)