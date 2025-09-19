from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import uvicorn
from database import execute_sql
from text2sql import Text2SQLGenerator
from schema_vectorizer import SchemaVectorizer
from config import APP_CONFIG, LOGGING_CONFIG
import logging
import os
import json
import threading
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

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

# Mount static files for simple frontend UI
if not os.path.isdir("static"):
    os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Initialize core components
text2sql_generator = Text2SQLGenerator()
schema_vectorizer = SchemaVectorizer()

# Local user config storage
CONFIG_FILE = "user_configs.json"
_config_lock = threading.Lock()
_conversations: Dict[str, List[Dict[str, str]]] = {}

SYSTEM_PROMPT = "You are a helpful assistant that outputs only MySQL SQL queries without any explanation unless the user intent is conversational, in which case respond briefly in Chinese."

def _get_conversation(username: str) -> List[Dict[str, str]]:
    conv = _conversations.get(username)
    if not conv:
        conv = [{"role": "system", "content": SYSTEM_PROMPT}]
        _conversations[username] = conv
    return conv

class QueryRequest(BaseModel):
    question: str
    max_retries: Optional[int] = 8
    username: str

class QueryResponse(BaseModel):
    success: bool
    sql_query: str
    results: Optional[List[Dict[str, Any]]] = None
    columns: Optional[List[str]] = None
    error: Optional[str] = None
    retry_count: int
    assistant_message: Optional[str] = None

class UserConfigRequest(BaseModel):
    """Per-user configuration payload"""
    username: str
    mysql_host: str
    mysql_port: int
    mysql_password: str
    mysql_user: Optional[str] = None
    openai_base_url: str
    openai_model: str
    openai_api_key: str
    embedding_base_url: str
    embedding_model: str
    embedding_api_key: str

def _load_user_config(username: str) -> Dict[str, Any]:
    """Load specified user's config from local JSON file.
    Raises HTTPException if not found or invalid.
    """
    if not username:
        raise HTTPException(status_code=400, detail="username is required")
    if not os.path.exists(CONFIG_FILE):
        raise HTTPException(status_code=404, detail="user config store not found")
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f) or {}
        user_cfg = data.get(username)
        if not user_cfg:
            raise HTTPException(status_code=404, detail=f"no config found for user '{username}'")
        # Basic validation for required sections
        if "openai" not in user_cfg or "embedding" not in user_cfg:
            raise HTTPException(status_code=400, detail="user config missing 'openai' or 'embedding'")
        return user_cfg
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="user config store is corrupted")

@app.on_event("startup")
async def startup_event():
    """Initialize the system on startup"""
    print("Initializing NL2SQL System...")
    # Defer model/vector initialization to per-user requests
    print("NL2SQL System initialized successfully!")

@app.get("/")
async def root(username: str):
    return {"message": "NL2SQL Smart Query System is running!", "user": username}

@app.get("/ui")
async def ui():
    """Serve a simple frontend UI"""
    index_path = os.path.join("static", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    else:
        return {"message": "UI not found. Please ensure static/index.html exists."}

@app.get("/health")
async def health_check(username: str):
    """Health check endpoint"""
    try:
        # Test database connection
        test_result = execute_sql("SELECT 1 as test")
        if test_result["success"]:
            return {"status": "healthy", "database": "connected", "user": username}
        else:
            return {"status": "unhealthy", "database": "disconnected", "error": test_result["error"], "user": username}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e), "user": username}

@app.post("/user/config")
async def upsert_user_config(req: UserConfigRequest):
    """Upsert per-user configuration into local JSON file keyed by username.
    If username exists, update; otherwise insert a new entry.
    """
    try:
        with _config_lock:
            configs = {}
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    try:
                        configs = json.load(f) or {}
                    except json.JSONDecodeError:
                        configs = {}
            action = "created" if req.username not in configs else "updated"
            configs[req.username] = {
                "mysql": {
                    "host": req.mysql_host,
                    "port": req.mysql_port,
                    "password": req.mysql_password,
                    **({"user": req.mysql_user} if req.mysql_user else {})
                },
                "openai": {
                    "base_url": req.openai_base_url,
                    "model": req.openai_model,
                    "api_key": req.openai_api_key,
                },
                "embedding": {
                    "base_url": req.embedding_base_url,
                    "model": req.embedding_model,
                    "api_key": req.embedding_api_key,
                },
            }

            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(configs, f, ensure_ascii=False, indent=2)

        return {"message": f"User config {action} successfully", "action": action}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upsert user config: {str(e)}")

@app.get("/user/config")
async def get_user_config(username: str):
    """Check whether a user's config exists. Do not return secrets; only existence flag."""
    try:
        with _config_lock:
            if not os.path.exists(CONFIG_FILE):
                return {"exists": False}
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                configs = json.load(f) or {}
            exists = username in configs
            return {"exists": exists}
    except json.JSONDecodeError:
        return {"exists": False}

@app.post("/query", response_model=QueryResponse)
async def natural_language_query(request: QueryRequest):
    """
    Main endpoint for natural language to SQL conversion and execution
    """
    try:
        # Prepare conversation memory
        conv = _get_conversation(request.username)
        # Append current user utterance
        conv.append({"role": "user", "content": request.question})

        # Load per-user config and initialize models
        user_cfg = _load_user_config(request.username)
        text2sql_generator.initialize_with_user_config(user_cfg, username=request.username)
        # Use the text2sql generator with self-healing loop
        result = text2sql_generator.generate_and_execute(
            question=request.question,
            max_retries=request.max_retries,
            messages=conv,
        )
        
        return QueryResponse(
            success=result["success"],
            sql_query=result.get("final_sql", ""),
            results=result.get("data"),
            columns=result.get("columns"),
            error=result.get("error"),
            retry_count=result.get("retry_count", 0),
            assistant_message=result.get("assistant_message")
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/schema/refresh")
async def refresh_schema(username: str):
    """Refresh the schema information in the vector database"""
    try:
        user_cfg = _load_user_config(username)
        vec = SchemaVectorizer()
        vec.initialize_with_user_config(user_cfg, username)
        vec.refresh_schema()
        return {"message": "Schema refreshed successfully", "user": username}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to refresh schema: {str(e)}")

@app.get("/schema/tables")
async def get_tables(username: str):
    """Get list of available tables in the database"""
    try:
        result = execute_sql("SHOW TABLES")
        if result["success"]:
            tables = [list(row.values())[0] for row in result["data"]]
            return {"tables": tables, "user": username}
        else:
            raise HTTPException(status_code=500, detail=result["error"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/schema/info")
async def get_schema_info_cached(username: str):
    """Return the cached database schema used for retrieval.
    If cache is empty, attempt a safe refresh once.
    """
    try:
        user_cfg = _load_user_config(username)
        vec = SchemaVectorizer()
        vec.initialize_with_user_config(user_cfg, username)
        # If cache is empty, try to refresh once (non-fatal if it fails)
        if not vec.schema_cache:
            try:
                vec.refresh_schema()
            except Exception as refresh_err:
                logger.warning(f"Schema refresh failed during /schema/info for {username}: {refresh_err}")

        if vec.schema_cache:
            return {
                "count": len(vec.schema_cache),
                "schemas": vec.schema_cache,
                "user": username,
            }
        else:
            return {
                "count": 0,
                "schemas": {},
                "message": "Schema cache is empty. Ensure database is reachable and call /schema/refresh.",
                "user": username,
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