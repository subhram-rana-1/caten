#!/bin/bash

# Caten API Startup Script
set -e

echo "Starting Caten API Server..."

# Check if .env file exists
if [ ! -f .env ]; then
    echo "Error: .env file not found."
    echo "Please create a .env file with your configuration before running the application."
    exit 1
fi

# Load environment variables
export $(grep -v '^#' .env | xargs)

# Check required environment variables
if [ -z "$OPENAI_API_KEY" ]; then
    echo "Error: OPENAI_API_KEY is required but not set in .env file"
    exit 1
fi

# Create logs directory
mkdir -p logs

# Check if Redis is required and running
if [ "$ENABLE_RATE_LIMITING" = "true" ]; then
    echo "Checking Redis connection..."
    if ! redis-cli -u "$REDIS_URL" ping > /dev/null 2>&1; then
        echo "Warning: Redis is not accessible. Rate limiting will be disabled."
        echo "To enable rate limiting, ensure Redis is running at: $REDIS_URL"
    fi
fi

# Install dependencies if venv doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install/upgrade dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Run database migrations (if any)
# python -m alembic upgrade head

# Start the server based on environment
if [ "$DEBUG" = "true" ]; then
    echo "Starting development server..."
    uvicorn app.main:app --reload --host "$HOST" --port "$PORT" --log-level "$LOG_LEVEL"
else
    echo "Starting production server..."
    gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind "$HOST:$PORT" --log-level "$LOG_LEVEL"
fi
