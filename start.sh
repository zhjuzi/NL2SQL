#!/bin/bash

# NL2SQL System Startup Script

echo "==================================="
echo "NL2SQL Smart Query System"
echo "==================================="
echo ""

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed or not in PATH"
    exit 1
fi

# Check if pip is available
if ! command -v pip3 &> /dev/null; then
    echo "❌ pip3 is not installed or not in PATH"
    exit 1
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "⚠️  .env file not found. Creating from .env.example..."
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "✅ Created .env file from .env.example"
        echo "⚠️  Please edit .env file with your configuration before continuing"
        echo "   - Set your MySQL database credentials"
        echo "   - Set your OpenAI API key"
        exit 1
    else
        echo "❌ .env.example file not found"
        exit 1
    fi
fi

# Check if required packages are installed
echo "Checking dependencies..."
if [ ! -f "requirements_installed.flag" ]; then
    echo "Installing required packages..."
    pip3 install -r requirements.txt
    if [ $? -eq 0 ]; then
        touch requirements_installed.flag
        echo "✅ Dependencies installed successfully"
    else
        echo "❌ Failed to install dependencies"
        exit 1
    fi
else
    echo "✅ Dependencies already installed"
fi

# Test database connection
echo "Testing database connection..."
python3 -c "
import sys
try:
    from database import test_connection
    if test_connection():
        print('✅ Database connection successful')
    else:
        print('❌ Database connection failed')
        sys.exit(1)
except Exception as e:
    print(f'❌ Database connection error: {e}')
    sys.exit(1)
"

if [ $? -ne 0 ]; then
    echo ""
    echo "⚠️  Database connection failed. Please check:"
    echo "   - Is your MySQL container running? (docker ps)"
    echo "   - Are the database credentials correct in .env?"
    echo "   - Is the port mapping correct?"
    exit 1
fi

# Check if OpenAI API key is set
if grep -q "OPENAI_API_KEY=your_openai_api_key_here" .env; then
    echo "⚠️  Please set your OpenAI API key in the .env file"
    echo "   Get your API key from: https://platform.openai.com/account/api-keys"
    exit 1
else
    # Also handle case when variable not present at all
    if ! grep -q "^OPENAI_API_KEY=" .env; then
        echo "⚠️  OPENAI_API_KEY is missing from .env. Please add it."
        echo "   Get your API key from: https://platform.openai.com/account/api-keys"
        exit 1
    fi
    echo "✅ OpenAI API key appears to be configured"
fi

# Start the application
echo ""
echo "Starting NL2SQL server..."
echo "==================================="
echo "Server will be available at: http://localhost:8000"
echo "API documentation: http://localhost:8000/docs"
echo "Health check: http://localhost:8000/health"
echo ""
echo "Press Ctrl+C to stop the server"
echo "==================================="
echo ""

# Start the FastAPI application
python3 main.py