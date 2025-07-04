#!/bin/bash

# HW Buddy Live Server Startup Script

echo "🚀 Starting HW Buddy Live Backend with ADK Live Agent..."
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

# Start the server
echo "🎯 Starting ADK Live server on port 8000..."
echo ""
echo "New Features:"
echo "  • ADK Live Agent with real-time audio streaming"
echo "  • Direct image upload from mobile app" 
echo "  • Bidirectional WebSocket audio communication"
echo ""
echo "Endpoints:"
echo "  • Audio WebSocket: ws://localhost:8000/ws/audio/{session_id}"
echo "  • Image Upload: POST /sessions/{session_id}/upload_image"
echo "  • Session Management: POST /sessions, GET /sessions/{id}/status"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Start the server with uvicorn
python main_live.py

echo ""
echo "✅ Server stopped"