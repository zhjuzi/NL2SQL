# NL2SQL Smart Query System

A natural language to SQL query system with self-healing capabilities, powered by Large Language Models and vector databases.

## Features

- 🎯 **Natural Language to SQL**: Convert natural language questions into executable SQL queries
- 🔧 **Self-Healing**: Automatically fix SQL errors and retry execution
- 🧠 **Smart Schema Matching**: Use vector similarity to find relevant database tables
- 🗣️ **Multi-language Support**: Optimized for Chinese natural language queries
- 🔍 **Schema Visualization**: Automatic database schema extraction and vectorization
- ⚡ **FastAPI Backend**: High-performance REST API

## Architecture

The system consists of several key components:

1. **FastAPI Backend**: REST API server
2. **Database Module**: MySQL connection and query execution
3. **Schema Vectorizer**: Extracts and vectorizes database schema for similarity search
4. **Text2SQL Generator**: Converts natural language to SQL with self-healing capabilities
5. **ChromaDB**: Vector database for schema similarity search
6. **OpenAI**: Large Language Model for SQL generation

## Prerequisites

- Python 3.8+
- MySQL database (running in Docker or locally)
- OpenAI API key
- (Optional) OpenAI Base URL

## Setup Instructions

### 1. MySQL Database Setup

If you're using Docker (as mentioned), make sure your MySQL container is running:

```bash
# Check if MySQL container is running
docker ps

# Example MySQL Docker run command (adjust as needed)
docker run -d --name mysql-container \
  -e MYSQL_ROOT_PASSWORD=password \
  -e MYSQL_DATABASE=test_db \
  -p 3307:3306 \
  mysql:8.0
```

### 2. Environment Configuration

1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Edit `.env` file with your configuration:
```bash
# MySQL Database Configuration
DB_HOST=127.0.0.1
DB_PORT=3307
DB_USER=root
DB_PASSWORD=password
DB_NAME=test_db

# OpenAI API Key
OPENAI_API_KEY=your_openai_api_key_here

# Optional: OpenAI Base URL (for Azure/OpenAI-compatible gateways). Default is https://api.openai.com/v1
OPENAI_BASE_URL=https://api.openai.com/v1
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the Application

```bash
python main.py
```

The API will be available at `http://localhost:8000`

## API Endpoints

### Health Check
```http
GET /health
```

### Natural Language Query
```http
POST /query
Content-Type: application/json

{
  "question": "Show me all customers",
  "max_retries": 3
}
```

### Refresh Schema
```http
GET /schema/refresh
```

### Get Available Tables
```http
GET /schema/tables
```

## Usage Examples

### Basic Query
```bash
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Show me all customers from Beijing"
  }'
```

### Query with Custom Retry Count
```bash
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Find the top 5 most expensive products",
    "max_retries": 5
  }'
```

### Chinese Language Query (Optimized)
```bash
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "查询客户风险模块大理矿业公司负责人身份证号"
  }'
```

## Database Configuration

### Connection Settings
Update the database connection settings in `database.py`:

```python
DB_CONFIG = {
    'host': '127.0.0.1',    # Your MySQL host
    'port': 3307,           # Your MySQL port
    'user': 'root',         # Your MySQL username
    'password': 'password', # Your MySQL password
    'database': 'test_db',  # Your database name
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}
```

### Docker MySQL Connection

If your MySQL is running in Docker, ensure:
1. The container is running: `docker ps`
2. Port mapping is correct (e.g., `-p 3307:3306`)
3. The host is set to `127.0.0.1` or `localhost`
4. Use the mapped port (3307 in the example)

## Schema Vectorization

The system automatically extracts and vectorizes your database schema for better query matching. To refresh the schema:

```bash
curl "http://localhost:8000/schema/refresh"
```

## Self-Healing Mechanism

The system includes a self-healing mechanism that:
1. Captures SQL execution errors
2. Analyzes the error message
3. Generates a corrected SQL query
4. Retries execution up to the specified retry count

## Configuration Options

### LLM Configuration
The system uses OpenAI API. Configure your API key in the `.env` file:
```
OPENAI_API_KEY=your_openai_api_key_here
```

Optionally, you can specify a custom base URL (e.g., for Azure OpenAI or an OpenAI-compatible proxy):
```
OPENAI_BASE_URL=https://api.openai.com/v1
```

### Vector Database
ChromaDB is used for schema vectorization. Data is stored in the `./chroma_db` directory.

### Retry Logic
You can configure the maximum retry attempts per query:
- Default: 3 retries
- Configurable per query via the `max_retries` parameter

## Development

### Project Structure
```
NL2SQL/
├── main.py                 # FastAPI application
├── database.py             # MySQL connection and query execution
├── schema_vectorizer.py    # Schema extraction and vectorization
├── text2sql.py             # Text to SQL conversion with self-healing
├── requirements.txt        # Python dependencies
├── .env.example           # Environment configuration example
└── README.md              # This file
```

### Running Tests
```bash
pytest
```

### Code Formatting
```bash
black .
isort .
```

## Troubleshooting

### Database Connection Issues
1. Check if MySQL container is running: `docker ps`
2. Verify port mapping in Docker
3. Check database credentials in `.env`
4. Test connection: `curl "http://localhost:8000/health"`

### Schema Vectorization Issues
1. Ensure ChromaDB directory has write permissions
2. Check if schema refresh endpoint returns success
3. Verify database connection is working

### LLM Issues
1. Verify OpenAI API key is set correctly
2. Check API quota and limits
3. Monitor API response times

### SQL Generation Issues
1. Check database schema comments and descriptions
2. Verify table relationships are properly defined
3. Review LLM prompt templates in `text2sql.py`

## Security Considerations

- Always use read-only database users for production
- Implement proper input validation
- Monitor and log all queries
- Use environment variables for sensitive configuration
- Consider implementing query timeouts
- Add rate limiting for API endpoints

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

This project is open source. Please check the license file for details.

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review the logs for error messages
3. Open an issue on the project repository