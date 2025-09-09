import os
import logging
from typing import Dict, List, Any, Optional
from openai import OpenAI
from database import execute_sql
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
        """Initialize the Text2SQL generator"""
        try:
            # Initialize OpenAI client
            # Prefer environment variable OPENAI_API_KEY; fallback to config
            api_key = os.getenv("OPENAI_API_KEY") or LLM_CONFIG.get("openai_api_key", "")
            if not api_key:
                raise ValueError("OPENAI_API_KEY is not set. Please configure it in environment or .env file.")
            base_url = LLM_CONFIG.get("base_url")
            # Create client with optional base_url (useful for Azure OpenAI or proxies)
            if base_url:
                self.client = OpenAI(api_key=api_key, base_url=base_url)
            else:
                self.client = OpenAI(api_key=api_key)
            self.model_name = LLM_CONFIG['model_name']
            
            # Initialize schema vectorizer
            self.schema_vectorizer.initialize()
            
            logger.info("Text2SQLGenerator initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Text2SQLGenerator: {str(e)}")
            raise

    def generate_and_execute(self, question: str, max_retries: int = 3) -> Dict[str, Any]:
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
            
            for attempt in range(max_retries):
                logger.info(f"--- Attempt {attempt + 1} ---")
                retry_count = attempt
                
                # 1. Search for relevant schema
                relevant_schemas = self.schema_vectorizer.search_relevant_schema(question, n_results=3)
                
                if not relevant_schemas:
                    logger.warning("No relevant schemas found, using all available schemas")
                    schema_info = self._get_all_schema_text()
                else:
                    schema_info = self._format_schemas_for_prompt(relevant_schemas)
                
                # 2. Generate SQL using LLM
                if attempt == 0:
                    # First attempt - use initial prompt
                    current_sql = self._generate_initial_sql(question, schema_info)
                else:
                    # Subsequent attempts - use healing prompt
                    current_sql = self._generate_healing_sql(
                        question, schema_info, current_sql, last_error
                    )
                
                logger.info(f"Generated SQL: {current_sql}")
                
                # 3. Execute SQL
                result = execute_sql(current_sql)
                
                # 4. Check result
                if result["success"]:
                    logger.info("SQL executed successfully!")
                    return {
                        "success": True,
                        "final_sql": current_sql,
                        "data": result["data"],
                        "columns": result["columns"],
                        "retry_count": retry_count
                    }
                else:
                    logger.info("SQL execution failed, preparing to retry...")
                    last_error = result["error"]
                    
                    # If this is the last attempt, return the error
                    if attempt == max_retries - 1:
                        logger.error("Maximum retry attempts reached")
                        return {
                            "success": False,
                            "final_sql": current_sql,
                            "error": last_error,
                            "retry_count": retry_count
                        }
            
        except Exception as e:
            logger.error(f"Unexpected error in generate_and_execute: {str(e)}")
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}",
                "retry_count": retry_count
            }

    def _generate_initial_sql(self, question: str, schema_info: str) -> str:
        """Generate SQL using the initial prompt template"""
        try:
            user_prompt = self.initial_prompt_template.format(
                retrieved_schema=schema_info,
                user_question=question
            )

            completion = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that outputs only MySQL SQL queries without any explanation."},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=LLM_CONFIG.get("max_tokens", 2048),
                temperature=0.1,
            )
            content = completion.choices[0].message.content or ""
            sql_query = self._extract_sql_from_response(content)
            
            return sql_query
            
        except Exception as e:
            logger.error(f"Failed to generate initial SQL: {str(e)}")
            raise

    def _generate_healing_sql(self, question: str, schema_info: str, failed_sql: str, error_message: str) -> str:
        """Generate SQL using the healing prompt template"""
        try:
            user_prompt = self.healing_prompt_template.format(
                retrieved_schema=schema_info,
                user_question=question,
                failed_sql=failed_sql,
                error_message=error_message
            )

            completion = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that outputs only corrected MySQL SQL queries without any explanation."},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=LLM_CONFIG.get("max_tokens", 2048),
                temperature=0.1,
            )
            content = completion.choices[0].message.content or ""
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