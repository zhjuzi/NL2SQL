from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import uvicorn
from database import execute_sql
from text2sql import Text2SQLGenerator
from schema_vectorizer import SchemaVectorizer
from config import APP_CONFIG, LOGGING_CONFIG
import logging

# Configure logging
logging.basicConfig(
    level=getattr(logging, LOGGING_CONFIG['level']),
    format=LOGGING_CONFIG['format']
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="NL2SQL Smart Query System",
    description="Natural Language to SQL query system with self-healing capabilities",
    version="1.0.0"
)

# Initialize core components
text2sql_generator = Text2SQLGenerator()
schema_vectorizer = SchemaVectorizer()

class QueryRequest(BaseModel):
    question: str
    max_retries: Optional[int] = 3

class QueryResponse(BaseModel):
    success: bool
    sql_query: str
    results: Optional[List[Dict[str, Any]]] = None
    columns: Optional[List[str]] = None
    error: Optional[str] = None
    retry_count: int

@app.on_event("startup")
async def startup_event():
    """Initialize the system on startup"""
    print("Initializing NL2SQL System...")
    # Initialize schema vectorizer and load schema data
    schema_vectorizer.initialize()
    print("NL2SQL System initialized successfully!")

@app.get("/")
async def root():
    return {"message": "NL2SQL Smart Query System is running!"}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        test_result = execute_sql("SELECT 1 as test")
        if test_result["success"]:
            return {"status": "healthy", "database": "connected"}
        else:
            return {"status": "unhealthy", "database": "disconnected", "error": test_result["error"]}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

@app.post("/query", response_model=QueryResponse)
async def natural_language_query(request: QueryRequest):
    """
    Main endpoint for natural language to SQL conversion and execution
    """
    try:
        # Use the text2sql generator with self-healing loop
        result = text2sql_generator.generate_and_execute(
            question=request.question,
            max_retries=request.max_retries
        )
        
        return QueryResponse(
            success=result["success"],
            sql_query=result.get("final_sql", ""),
            results=result.get("data"),
            columns=result.get("columns"),
            error=result.get("error"),
            retry_count=result.get("retry_count", 0)
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/schema/refresh")
async def refresh_schema():
    """Refresh the schema information in the vector database"""
    try:
        schema_vectorizer.refresh_schema()
        return {"message": "Schema refreshed successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to refresh schema: {str(e)}")

@app.get("/schema/tables")
async def get_tables():
    """Get list of available tables in the database"""
    try:
        result = execute_sql("SHOW TABLES")
        if result["success"]:
            tables = [list(row.values())[0] for row in result["data"]]
            return {"tables": tables}
        else:
            raise HTTPException(status_code=500, detail=result["error"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/schema/info")
async def get_schema_info_cached():
    """Return the cached database schema used for retrieval.
    If cache is empty, attempt a safe refresh once.
    """
    try:
        # If cache is empty, try to refresh once (non-fatal if it fails)
        if not schema_vectorizer.schema_cache:
            try:
                schema_vectorizer.refresh_schema()
            except Exception as refresh_err:
                # Do not fail the request solely due to refresh error
                logger.warning(f"Schema refresh failed during /schema/info: {refresh_err}")

        if schema_vectorizer.schema_cache:
            return {
                "count": len(schema_vectorizer.schema_cache),
                "schemas": schema_vectorizer.schema_cache
            }
        else:
            return {
                "count": 0,
                "schemas": {},
                "message": "Schema cache is empty. Ensure database is reachable and call /schema/refresh."
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(
        app, 
        host=APP_CONFIG['host'], 
        port=APP_CONFIG['port'],
        # reload=True
    )