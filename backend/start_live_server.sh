#!/bin/bash

# HW Buddy Live Server Startup Script

echo "🚀 Starting HW Buddy Optimized Backend with Event-Based Processing..."
echo ""

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "❌ Virtual environment not found. Please run:"
    echo "   uv sync"
    echo "   source .venv/bin/activate"
    exit 1
fi

# Check if environment file exists
if [ ! -f ".env" ]; then
    echo "⚠️  .env file not found. Copying from .env.example..."
    cp .env.example .env
    echo "✅ Please edit .env with your configuration"
fi

# Activate virtual environment if not already active
if [ -z "$VIRTUAL_ENV" ]; then
    echo "📦 Activating virtual environment..."
    source .venv/bin/activate
fi

# Load environment variables from .env file
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Check if required environment variables are set
if [ -z "$GOOGLE_CLOUD_PROJECT" ] && [ -z "$GOOGLE_AI_API_KEY" ]; then
    echo "⚠️  Please set GOOGLE_CLOUD_PROJECT and GOOGLE_AI_API_KEY in .env"
    echo "   Or ensure GOOGLE_APPLICATION_CREDENTIALS is set"
fi

# Set Firebase project for mobile app integration
export GOOGLE_CLOUD_PROJECT="hw-buddy-66d6b"

# Start the server
echo "🎯 Starting optimized server on port 8000..."
echo ""
echo "Latest Features:"
echo "  • Real Gemini 2.0 Flash image analysis (replaces hardcoded responses)"
echo "  • Live audio streaming with ADK Live API"
echo "  • Smart MathJax extraction from homework images"
echo "  • Optimized WebSocket communication"
echo ""
echo "Endpoints:"
echo "  • WebSocket: ws://localhost:8000/ws/audio/{session_id}"
echo "  • Image Upload: POST /take_picture" 
echo "  • Health Check: GET /health"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Start the server with uvicorn (using live backend with working audio)
python main_live.py

echo ""
echo "✅ Server stopped"