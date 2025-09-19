import os
import logging
from typing import Dict, List, Any, Optional
from openai import OpenAI
from database import execute_sql_with_overrides
from schema_vectorizer import SchemaVectorizer
from config import LLM_CONFIG, APP_CONFIG

# Configure logging
logger = logging.getLogger(__name__)

class Text2SQLGenerator:
    """
    Handles natural language to SQL conversion with self-healing capabilities
    """
    
    def __init__(self):
        self.client = None
        self.model_name = None
        self.schema_vectorizer = SchemaVectorizer()
        self._initialized_user = None
        self._db_overrides: Optional[Dict[str, Any]] = None
        self.initial_prompt_template = """
### Instructions ###
You are a MySQL expert. Your task is to generate a SQL query based on the user's question and the provided database schema.
Only use the tables and columns provided in the schema.
The user's question is in Chinese. Please generate a single, executable MySQL query. Do not add any explanations or comments in the SQL itself.

### Database Schema ###
{retrieved_schema}

### User Question ###
{user_question}

### SQL Query ###
"""
        
        self.healing_prompt_template = """
### Instructions ###
You are a MySQL expert. You previously generated a SQL query that failed to execute. Your task is to fix the query based on the error message.
Only use the tables and columns provided in the schema.
The user's question is in Chinese. Please generate a single, executable MySQL query. Do not add any explanations or comments in the SQL itself.

### Database Schema ###
{retrieved_schema}

### User Question ###
{user_question}

### Previous Failed SQL ###
{failed_sql}

### MySQL Error Message ###
{error_message}

### Corrected SQL Query ###
"""

    def initialize(self):
        """Initialize the Text2SQL generator using default config (backward-compatible)."""
        try:
            api_key = os.getenv("OPENAI_API_KEY") or LLM_CONFIG.get("openai_api_key", "")
            if not api_key:
                raise ValueError("OPENAI_API_KEY is not set. Please configure it in environment or .env file.")
            base_url = LLM_CONFIG.get("base_url")
            self.client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
            self.model_name = LLM_CONFIG['model_name']

            self.schema_vectorizer.initialize()

            logger.info("Text2SQLGenerator initialized successfully (default config)")
        except Exception as e:
            logger.error(f"Failed to initialize Text2SQLGenerator: {str(e)}")
            raise

    def initialize_with_user_config(self, user_cfg: Dict[str, Any], username: Optional[str] = None):
        """Initialize using per-user configuration.

        user_cfg structure example:
        {
          "openai": {"base_url": str, "model": str, "api_key": str},
          "embedding": {"base_url": str, "model": str, "api_key": str}
        }
        """
        try:
            oa = user_cfg.get("openai", {}) if user_cfg else {}
            api_key = oa.get("api_key")
            base_url = oa.get("base_url")
            model = oa.get("model")
            if not api_key or not model:
                raise ValueError("Per-user OpenAI config missing 'api_key' or 'model'")

            self.client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
            self.model_name = model

            # Initialize schema vectorizer with embedding config (per user)
            self.schema_vectorizer.initialize_with_user_config(user_cfg, username=username or "")

            # Store DB overrides for tool execution
            mysql_cfg = (user_cfg or {}).get("mysql", {})
            self._db_overrides = {
                k: mysql_cfg.get(k)
                for k in ("host", "port", "user", "password", "database", "charset")
                if mysql_cfg.get(k) is not None
            }

            self._initialized_user = username
            logger.info("Text2SQLGenerator initialized successfully (per-user config)")
        except Exception as e:
            logger.error(f"Failed to initialize Text2SQLGenerator with user config: {str(e)}")
            raise

    def generate_and_execute(self, question: str, max_retries: int = 8, messages: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
        """
        Main method to generate SQL from natural language and execute with self-healing
        
        Args:
            question: User's natural language question
            max_retries: Maximum number of retry attempts
            
        Returns:
            Dict containing execution results
        """
        try:
            # Lazy initialize if not already initialized
            if self.client is None or not self.model_name:
                self.initialize()

            current_sql = ""
            last_error = ""
            retry_count = 0
            # Conversation messages array (reuse caller-provided if given)
            if messages is None:
                messages = [
                    {"role": "system", "content": "You are a helpful assistant that outputs only MySQL SQL queries without any explanation."}
                ]
            # Build a retrieval-aware SYSTEM guidance so the model understands available tools,
            # while still allowing normal conversational replies when appropriate.
            relevant_schemas = self.schema_vectorizer.search_relevant_schema(question, n_results=3)
            if not relevant_schemas:
                schema_info = self._get_all_schema_text()
            else:
                schema_info = self._format_schemas_for_prompt(relevant_schemas)
            tool_guide = (
                "你是一个 NL2SQL 智能体。你可以：\n"
                "- 直接以中文自然语言回复用户（当用户是闲聊或无需数据库时）。\n"
                "- 当需要数据库时，可调用以下工具：\n"
                "  1) execute_sql(sql): 执行 MySQL 并返回结果\n"
                "  2) get_table_schema(table): 查询某表的列与 DDL\n"
                "  3) get_related_table_schemas(table, n_results): 通过向量检索相关表\n"
                "请自行决策是否需要调用工具。若生成 SQL，确保是可执行的 MySQL。\n\n"
                "近期可用的数据库结构概览：\n" + (schema_info[:2000] if schema_info else "(暂无)"))
            messages.append({"role": "system", "content": tool_guide})

            tools = [
                {
                    "type": "function",
                    "function": {
                        "name": "execute_sql",
                        "description": "Execute a MySQL SQL query and return rows and columns.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "sql": {"type": "string", "description": "The SQL query to execute."}
                            },
                            "required": ["sql"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "get_table_schema",
                        "description": "Get DDL and columns for a specific table directly from MySQL.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "table": {"type": "string", "description": "The table name to describe."}
                            },
                            "required": ["table"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "get_related_table_schemas",
                        "description": "Retrieve schemas of tables related to the given table using vector search (RAG).",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "table": {"type": "string", "description": "The anchor table name to find related schemas."},
                                "n_results": {"type": "integer", "description": "How many related schemas to return.", "default": 5}
                            },
                            "required": ["table"]
                        }
                    }
                }
            ]

            # Agent loop
            for attempt in range(max_retries):
                retry_count = attempt
                completion = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    tools=tools,
                    tool_choice="auto",
                    temperature=0.1,
                    max_tokens=LLM_CONFIG.get("max_tokens", 2048),
                )
                msg = completion.choices[0].message
                content = msg.content or ""
                tool_calls = getattr(msg, "tool_calls", None)

                # Append assistant turn (may include tool calls)
                assistant_entry: Dict[str, Any] = {"role": "assistant", "content": content}
                if tool_calls:
                    assistant_entry["tool_calls"] = [tc.model_dump() if hasattr(tc, "model_dump") else tc for tc in tool_calls]
                messages.append(assistant_entry)

                if tool_calls:
                    # Handle tool calls one by one and ALWAYS respond with a tool message per tool_call_id
                    last_success_exec: Optional[Dict[str, Any]] = None
                    import json as _json
                    for tc in tool_calls:
                        fname = getattr(tc.function, "name", None)
                        args = getattr(tc.function, "arguments", {})
                        try:
                            if isinstance(args, str):
                                args = _json.loads(args)
                        except Exception:
                            args = {}

                        try:
                            if fname == "execute_sql":
                                sql = (args.get("sql") or "").strip()
                                current_sql = sql
                                exec_result = execute_sql_with_overrides(sql, self._db_overrides)
                                tool_content = _json.dumps(exec_result, ensure_ascii=False)
                                messages.append({
                                    "role": "tool",
                                    "tool_call_id": tc.id,
                                    "name": "execute_sql",
                                    "content": tool_content,
                                })
                                if exec_result.get("success"):
                                    last_success_exec = exec_result
                                else:
                                    last_error = exec_result.get("error", "")

                            elif fname == "get_table_schema":
                                table = (args.get("table") or "").strip()
                                if not table:
                                    raise ValueError("table is required")
                                desc = execute_sql_with_overrides(f"DESCRIBE {table}", self._db_overrides)
                                create_stmt = execute_sql_with_overrides(f"SHOW CREATE TABLE {table}", self._db_overrides)
                                payload = {"table": table, "describe": desc, "create": create_stmt}
                                tool_content = _json.dumps(payload, ensure_ascii=False)
                                messages.append({
                                    "role": "tool",
                                    "tool_call_id": tc.id,
                                    "name": "get_table_schema",
                                    "content": tool_content,
                                })

                            elif fname == "get_related_table_schemas":
                                table = (args.get("table") or "").strip()
                                n = args.get("n_results") or 5
                                rel = self.schema_vectorizer.search_relevant_schema(table, n_results=n)
                                payload = {"table": table, "related": rel}
                                tool_content = _json.dumps(payload, ensure_ascii=False)
                                messages.append({
                                    "role": "tool",
                                    "tool_call_id": tc.id,
                                    "name": "get_related_table_schemas",
                                    "content": tool_content,
                                })
                            else:
                                # Unknown tool; respond with an error tool message
                                payload = {"success": False, "error": f"Unknown tool: {fname}"}
                                messages.append({
                                    "role": "tool",
                                    "tool_call_id": tc.id,
                                    "name": fname or "unknown",
                                    "content": _json.dumps(payload, ensure_ascii=False),
                                })
                        except Exception as e:
                            # Return a tool message with the error for this tool_call_id
                            err_payload = {"success": False, "error": str(e)}
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tc.id,
                                "name": fname or "unknown",
                                "content": _json.dumps(err_payload, ensure_ascii=False),
                            })

                    # After providing tool messages for all tool calls, let the model respond next iteration
                    # If we have a successful execute_sql result, we can remember it to include in final response
                    if last_success_exec is not None:
                        # Attach a brief note for the model (as system) to summarize
                        messages.append({"role": "system", "content": "已返回 SQL 执行结果，请根据需要继续回答或提出下一步操作。"})
                    continue

                # No tool call; consider this a final assistant answer (e.g., small talk or explanation)
                if content:
                    return {
                        "success": True,
                        "final_sql": current_sql or "",
                        "data": None,
                        "columns": None,
                        "retry_count": retry_count,
                        "assistant_message": content,
                    }

            # If exhausted attempts
            return {
                "success": False,
                "final_sql": current_sql,
                "error": last_error or "Max attempts reached without successful execution",
                "retry_count": retry_count,
            }
            
        except Exception as e:
            logger.error(f"Unexpected error in generate_and_execute: {str(e)}")
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}",
                "retry_count": retry_count
            }

    def _generate_initial_sql(self, question: str, schema_info: str, messages: List[Dict[str, str]]) -> str:
        """Generate SQL using the initial prompt template, updating the messages array."""
        try:
            user_prompt = self.initial_prompt_template.format(
                retrieved_schema=schema_info,
                user_question=question
            )
            # Append user message
            messages.append({"role": "user", "content": user_prompt})

            completion = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                max_tokens=LLM_CONFIG.get("max_tokens", 2048),
                temperature=0.1,
            )
            content = completion.choices[0].message.content or ""
            # Append assistant response to conversation
            messages.append({"role": "assistant", "content": content})
            sql_query = self._extract_sql_from_response(content)
            return sql_query
        except Exception as e:
            logger.error(f"Failed to generate initial SQL: {str(e)}")
            raise

    def _generate_healing_sql(self, question: str, schema_info: str, failed_sql: str, error_message: str, messages: List[Dict[str, str]]) -> str:
        """Generate SQL using the healing prompt template, updating the messages array."""
        try:
            user_prompt = self.healing_prompt_template.format(
                retrieved_schema=schema_info,
                user_question=question,
                failed_sql=failed_sql,
                error_message=error_message
            )
            # Use a concise system reminder once at the start already present; just append user prompt
            messages.append({"role": "user", "content": user_prompt})

            completion = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                max_tokens=LLM_CONFIG.get("max_tokens", 2048),
                temperature=0.1,
            )
            content = completion.choices[0].message.content or ""
            # Append assistant response
            messages.append({"role": "assistant", "content": content})
            sql_query = self._extract_sql_from_response(content)
            return sql_query
        except Exception as e:
            logger.error(f"Failed to generate healing SQL: {str(e)}")
            raise

    def _format_schemas_for_prompt(self, schemas: List[Dict[str, Any]]) -> str:
        """Format schema information for the prompt"""
        formatted = []
        
        for schema in schemas:
            formatted.append(schema["schema_text"])
            formatted.append("")  # Add spacing between schemas
        
        return "\n".join(formatted)

    def _get_all_schema_text(self) -> str:
        """Get all schema information as text"""
        all_schemas = self.schema_vectorizer.get_all_schemas()
        formatted = []
        
        for table_name, table_info in all_schemas.items():
            if table_info.get("create_statement"):
                formatted.append(table_info["create_statement"])
                formatted.append("")
        
        return "\n".join(formatted)

    def _extract_sql_from_response(self, response_text: str) -> str:
        """Extract SQL query from the LLM response"""
        try:
            # Remove any markdown code blocks
            sql_query = response_text.strip()
            
            # Remove ```sql or ``` markers if present
            if sql_query.startswith("```sql"):
                sql_query = sql_query[6:]
            elif sql_query.startswith("```"):
                sql_query = sql_query[3:]
            
            if sql_query.endswith("```"):
                sql_query = sql_query[:-3]
            
            # Clean up the SQL
            sql_query = sql_query.strip()
            
            # Remove any comments or explanations that might be after the SQL
            lines = sql_query.split('\n')
            sql_lines = []
            
            for line in lines:
                line = line.strip()
                if line and not line.startswith('--') and not line.startswith('#'):
                    sql_lines.append(line)
            
            return ' '.join(sql_lines)
            
        except Exception as e:
            logger.error(f"Failed to extract SQL from response: {str(e)}")
            logger.error(f"Response text: {response_text}")
            raise

    def validate_sql_safety(self, sql_query: str) -> bool:
        """
        Basic SQL safety validation to prevent dangerous operations
        
        Args:
            sql_query: The SQL query to validate
            
        Returns:
            True if safe, False otherwise
        """
        dangerous_keywords = [
            'DROP', 'TRUNCATE', 'ALTER', 'CREATE USER', 'GRANT', 
            'REVOKE', 'KILL', 'SHUTDOWN', 'EXECUTE', 'LOAD_FILE'
        ]
        
        sql_upper = sql_query.upper()
        
        for keyword in dangerous_keywords:
            if keyword in sql_upper:
                logger.warning(f"Potentially dangerous SQL keyword detected: {keyword}")
                return False
        
        return True

# Example usage for testing
if __name__ == "__main__":
    generator = Text2SQLGenerator()
    generator.initialize()
    
    # Test query
    result = generator.generate_and_execute("Show me all customers")
    print(f"Success: {result['success']}")
    if result['success']:
        print(f"SQL: {result['final_sql']}")
        print(f"Results: {result['data']}")
    else:
        print(f"Error: {result['error']}")