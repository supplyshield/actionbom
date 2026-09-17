#!/bin/bash
# Quick start script for the ActionBOM Backend

set -e  # Exit on error

echo "🚀 Starting ActionBOM Backend..."
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Creating from .env.example..."
    cp .env.example .env
    echo "📝 Please edit .env with your configuration before running again:"
    echo "   1. Add your GITHUB_TOKEN"
    echo "   2. Verify DATABASE_URL is correct"
    echo ""
    exit 1
fi

# Check if GITHUB_TOKEN is set
if grep -q "^GITHUB_TOKEN=$" .env; then
    echo "⚠️  GITHUB_TOKEN not set in .env file"
    echo "📝 Please add your GitHub token to .env:"
    echo "   GITHUB_TOKEN=<TOKEN_HERE>"
    echo ""
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
    echo "✓ Virtual environment created"
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install/update dependencies
echo "📦 Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt
echo "✓ Dependencies installed"

# Test database connection
echo ""
echo "🔌 Testing database connection..."
python3 -c "
from app.config import settings
from sqlalchemy import create_engine, text
try:
    # Use psycopg2 driver for sync connection test
    test_url = settings.DATABASE_URL.replace('postgresql://', 'postgresql+psycopg2://')
    test_url = test_url.replace('postgresql+asyncpg://', 'postgresql+psycopg2://')
    engine = create_engine(test_url)
    with engine.connect() as conn:
        result = conn.execute(text('SELECT 1'))
        print('✓ Database connection successful')
except Exception as e:
    print(f'❌ Database connection failed: {e}')
    print('Please check your DATABASE_URL in .env')
    exit(1)
"

if [ $? -ne 0 ]; then
    exit 1
fi

# Check if Zizmor is installed
echo ""
echo "🔒 Checking for Zizmor (SAST scanner)..."
if command -v zizmor &> /dev/null; then
    ZIZMOR_VERSION=$(zizmor --version 2>&1 || echo "unknown")
    echo "✓ Zizmor found: $ZIZMOR_VERSION"
else
    echo "⚠️  Zizmor not installed (SAST scanning will be skipped)"
    echo "   Install with: cargo install zizmor"
fi

# Start the application
echo ""
echo "✓ All checks passed!"
echo "🚀 Starting FastAPI server..."
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  API:    http://localhost:8000"
echo "  Docs:   http://localhost:8000/docs"
echo "  Health: http://localhost:8000/api/health"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Run with uvicorn (reload enabled for development)
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
