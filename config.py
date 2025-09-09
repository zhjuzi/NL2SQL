import os
from dotenv import load_dotenv
from typing import Dict, Any

# Load environment variables
load_dotenv()

# Database Configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', '127.0.0.1'),
    'port': int(os.getenv('DB_PORT', '3307')),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', 'password'),
    'database': os.getenv('DB_NAME', 'test_db'),
    'charset': 'utf8mb4',
}

# Application Configuration
APP_CONFIG = {
    'host': os.getenv('APP_HOST', '0.0.0.0'),
    'port': int(os.getenv('APP_PORT', '8000')),
    'debug': os.getenv('DEBUG', 'true').lower() == 'true',
    'max_retries': int(os.getenv('MAX_RETRIES', '3'))
}

# LLM Configuration (OpenAI)
LLM_CONFIG = {
    'openai_api_key': os.getenv('OPENAI_API_KEY', 'sk-79bafa20b12240b090eba4c9cd2b5dbb'),
    'base_url': os.getenv('OPENAI_BASE_URL', os.getenv('OPENAI_API_BASE', 'https://dashscope.aliyuncs.com/compatible-mode/v1')),
    'model_name': os.getenv('LLM_MODEL', 'qwen-max'),
    'max_tokens': int(os.getenv('MAX_TOKENS', '2048'))
}

# Vector Database Configuration
VECTOR_DB_CONFIG = {
    'persist_directory': os.getenv('VECTOR_DB_PATH', './chroma_db'),
    'collection_name': os.getenv('VECTOR_COLLECTION', 'database_schema'),
    'embedding_model': os.getenv('EMBEDDING_MODEL', 'text-embedding-v4'),
    'embedding_dimensions': int(os.getenv('EMBEDDING_DIMENSIONS', '0')),
    'n_results': int(os.getenv('VECTOR_N_RESULTS', '5'))
}

# Logging Configuration
LOGGING_CONFIG = {
    'level': os.getenv('LOG_LEVEL', 'INFO'),
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
}

def validate_config():
    """Validate that all required configuration is present"""
    errors = []
    
    # Check required database configuration
    if not DB_CONFIG['user']:
        errors.append("DB_USER is required")
    if not DB_CONFIG['password']:
        errors.append("DB_PASSWORD is required")
    if not DB_CONFIG['database']:
        errors.append("DB_NAME is required")
    
    # Check LLM configuration
    if not LLM_CONFIG['openai_api_key']:
        errors.append("OPENAI_API_KEY is required")
    
    if errors:
        raise ValueError("Configuration validation failed:\n" + "\n".join(f"- {error}" for error in errors))

def get_config_summary():
    """Get a summary of the configuration (without sensitive data)"""
    return {
        'database': {
            'host': DB_CONFIG['host'],
            'port': DB_CONFIG['port'],
            'user': DB_CONFIG['user'],
            'database': DB_CONFIG['database'],
        },
        'application': {
            'host': APP_CONFIG['host'],
            'port': APP_CONFIG['port'],
            'debug': APP_CONFIG['debug'],
            'max_retries': APP_CONFIG['max_retries']
        },
        'llm': {
            'base_url': LLM_CONFIG.get('base_url'),
            'model_name': LLM_CONFIG['model_name'],
            'max_tokens': LLM_CONFIG['max_tokens']
        },
        'vector_db': {
            'persist_directory': VECTOR_DB_CONFIG['persist_directory'],
            'collection_name': VECTOR_DB_CONFIG['collection_name'],
            'n_results': VECTOR_DB_CONFIG['n_results']
        },
        'logging': {
            'level': LOGGING_CONFIG['level']
        }
    }

# Validate configuration on import
try:
    validate_config()
except ValueError as e:
    print(f"⚠️  Configuration Warning: {e}")
    print("Please set the required environment variables in your .env file")
    print("You can copy .env.example to .env and fill in the values")

if __name__ == "__main__":
    print("Configuration Summary:")
    print("=" * 50)
    
    config_summary = get_config_summary()
    for section, settings in config_summary.items():
        print(f"\n{section.upper()}:")
        for key, value in settings.items():
            print(f"  {key}: {value}")
    
    print("\n" + "=" * 50)
    print("Full configuration loaded successfully!")