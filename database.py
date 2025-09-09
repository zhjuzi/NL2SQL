import pymysql
from typing import Dict, Any, List
import logging
from config import DB_CONFIG

# Configure logging
logger = logging.getLogger(__name__)

def execute_sql(sql_query: str) -> Dict[str, Any]:
    """
    Execute SQL query and return results
    
    Args:
        sql_query: The SQL query to execute
        
    Returns:
        Dict containing success status, data, columns, and error message
    """
    connection = None
    try:
        # Establish connection (ensure DictCursor for dict-like rows)
        connection = pymysql.connect(
            cursorclass=pymysql.cursors.DictCursor,
            **DB_CONFIG
        )
        
        with connection.cursor() as cursor:
            # Execute SQL
            cursor.execute(sql_query)
            
            # Get query results
            result = cursor.fetchall()
            
            # Get column names
            if cursor.description:
                column_names = [i[0] for i in cursor.description]
            else:
                column_names = []
            
            # Commit for INSERT/UPDATE/DELETE operations
            if sql_query.strip().upper().startswith(('INSERT', 'UPDATE', 'DELETE')):
                connection.commit()
                logger.info(f"Successfully executed: {sql_query}")
            
            return {
                "success": True,
                "data": result,
                "columns": column_names,
                "error": None
            }

    except pymysql.MySQLError as e:
        # Capture all pymysql related errors
        error_code, error_message = e.args
        logger.error(f"SQL execution failed! Error code: {error_code}, Error message: {error_message}")
        return {
            "success": False,
            "data": None,
            "columns": None,
            "error": f"Error {error_code}: {error_message}"
        }
    except Exception as e:
        logger.error(f"Unexpected error during SQL execution: {str(e)}")
        return {
            "success": False,
            "data": None,
            "columns": None,
            "error": f"Unexpected error: {str(e)}"
        }
    finally:
        # Ensure connection is closed
        if connection:
            connection.close()

def test_connection() -> bool:
    """
    Test database connection
    
    Returns:
        True if connection is successful, False otherwise
    """
    try:
        result = execute_sql("SELECT 1 as test")
        return result["success"]
    except Exception as e:
        logger.error(f"Database connection test failed: {str(e)}")
        return False

def get_schema_info() -> Dict[str, Any]:
    """
    Get database schema information including tables and columns
    
    Returns:
        Dict containing schema information
    """
    try:
        # Get all tables
        tables_result = execute_sql("SHOW TABLES")
        if not tables_result["success"]:
            return tables_result
        
        schema_info = {}
        tables = [list(row.values())[0] for row in tables_result["data"]]
        
        for table in tables:
            # Get table structure
            columns_result = execute_sql(f"DESCRIBE {table}")
            if columns_result["success"]:
                schema_info[table] = {
                    "columns": columns_result["data"],
                    "create_statement": None
                }
                
                # Get CREATE TABLE statement
                create_result = execute_sql(f"SHOW CREATE TABLE {table}")
                if create_result["success"]:
                    schema_info[table]["create_statement"] = create_result["data"][0]["Create Table"]
        
        return {
            "success": True,
            "data": schema_info,
            "error": None
        }
    
    except Exception as e:
        logger.error(f"Failed to get schema info: {str(e)}")
        return {
            "success": False,
            "data": None,
            "error": f"Failed to get schema info: {str(e)}"
        }

def get_table_relationships() -> Dict[str, Any]:
    """
    Get table relationships (foreign keys) from information_schema
    
    Returns:
        Dict containing relationship information
    """
    try:
        relationships_query = """
        SELECT 
            TABLE_NAME,
            COLUMN_NAME,
            CONSTRAINT_NAME,
            REFERENCED_TABLE_NAME,
            REFERENCED_COLUMN_NAME
        FROM 
            information_schema.KEY_COLUMN_USAGE
        WHERE 
            TABLE_SCHEMA = DATABASE() 
            AND REFERENCED_TABLE_NAME IS NOT NULL
        """
        
        result = execute_sql(relationships_query)
        return result
    
    except Exception as e:
        logger.error(f"Failed to get table relationships: {str(e)}")
        return {
            "success": False,
            "data": None,
            "error": f"Failed to get table relationships: {str(e)}"
        }