#!/usr/bin/env python3

"""
HW Buddy WebSocket Server
WebSocket-based server that integrates Gemini Live API with image capture tools
"""

import logging
import asyncio
import os
import websockets
import json
from typing import Any
from dotenv import load_dotenv

from core.websocket_handler import handle_client

# Load environment variables from root project directory
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO').upper()),
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Suppress Google API client logs while keeping application debug messages
for logger_name in [
    'google',
    'google.auth',
    'google.auth.transport',
    'google.auth.transport.requests',
    'urllib3.connectionpool',
    'google.generativeai',
    'websockets.client',
    'websockets.protocol',
    'httpx',
    'httpcore',
]:
    logging.getLogger(logger_name).setLevel(logging.ERROR)

logger = logging.getLogger(__name__)

async def main() -> None:
    """Starts the WebSocket server."""
    port = int(os.getenv('WEBSOCKET_PORT', 8081))
    host = os.getenv('WEBSOCKET_HOST', '0.0.0.0')
    
    async with websockets.serve(
        handle_client,
        host,
        port,
        ping_interval=30,
        ping_timeout=10,
    ):
        logger.info(f"Running websocket server on {host}:{port}...")
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    asyncio.run(main())