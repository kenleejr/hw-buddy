#!/bin/bash

# HW Buddy Frontend Startup Script
# Updated for Backend Audio Integration

echo "🌐 Starting HW Buddy Frontend with Backend Audio Integration..."
echo ""

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "📦 Installing dependencies..."
    npm install
    echo ""
fi

# Check if .env.local exists
if [ ! -f ".env.local" ]; then
    echo "⚙️  Creating .env.local from example..."
    cp .env.example .env.local
    echo "✅ .env.local created with default settings"
    echo ""
fi

echo "🎯 Frontend Features:"
echo "  • Backend WebSocket audio streaming"
echo "  • Real-time bidirectional communication"
echo "  • Removed Gemini Live dependency"
echo "  • Direct backend ADK Live integration"
echo ""

echo "🔧 Configuration:"
echo "  • Backend URL: ws://localhost:8000"
echo "  • Input Audio: 16kHz PCM"
echo "  • Output Audio: 24kHz PCM"
echo ""

echo "📋 Requirements:"
echo "  • Backend server running on port 8000"
echo "  • Modern browser with WebSocket support"
echo "  • Microphone permission for audio input"
echo ""

echo "🚀 Starting development server on http://localhost:3000..."
echo "Press Ctrl+C to stop"
echo ""

# Start the development server
npm run dev