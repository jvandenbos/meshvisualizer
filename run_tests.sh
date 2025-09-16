#!/bin/bash

# Test runner script for Meshtastic Visualizer

set -e  # Exit on error

echo "🧪 Running Meshtastic Visualizer Test Suite"
echo "==========================================="
echo ""

# Check if virtual environment is active
if [ -z "$VIRTUAL_ENV" ]; then
    echo "⚠️  Virtual environment not active. Activating..."
    source venv/bin/activate
fi

# Install test dependencies if needed
echo "📦 Installing test dependencies..."
pip install -q pytest pytest-asyncio pytest-cov

echo ""
echo "🔧 Running tests..."
echo ""

# Run tests with coverage
pytest tests/ \
    -v \
    --cov=backend \
    --cov-report=term-missing \
    --cov-report=html:coverage_report \
    -W ignore::DeprecationWarning \
    "$@"

# Check exit code
if [ $? -eq 0 ]; then
    echo ""
    echo "✅ All tests passed!"
    echo ""
    echo "📊 Coverage report generated at: coverage_report/index.html"
else
    echo ""
    echo "❌ Some tests failed. Check the output above."
    exit 1
fi