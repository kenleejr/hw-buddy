"""
Audio WebSocket Server for HW Buddy Live Agent
Handles bidirectional audio streaming between frontend and ADK Live agent.
"""

import asyncio
import json
import logging
import base64
import traceback
from typing import Dict, Set
from fastapi import WebSocket, WebSocketDisconnect
from hw_live_agent import get_hw_live_agent

logger = logging.getLogger(__name__)


class AudioWebSocketManager:
    """Manages WebSocket connections for audio streaming."""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.session_tasks: Dict[str, asyncio.Task] = {}
        self.hw_agent = get_hw_live_agent()
    
    async def connect(self, websocket: WebSocket, session_id: str):
        """Accept a new WebSocket connection for audio streaming."""
        await websocket.accept()
        self.active_connections[session_id] = websocket
        logger.info(f"Audio WebSocket connected for session {session_id}")
        
        # Create session in the agent
        await self.hw_agent.create_session(session_id)
        
        # Start the ADK Live session
        await self._start_agent_session(session_id)
    
    def disconnect(self, session_id: str):
        """Disconnect and clean up a WebSocket connection."""
        if session_id in self.active_connections:
            del self.active_connections[session_id]
            logger.info(f"Audio WebSocket disconnected for session {session_id}")
        
        # Cancel session task if running
        if session_id in self.session_tasks:
            task = self.session_tasks[session_id]
            if not task.done():
                task.cancel()
                logger.info(f"Cancelled agent session task for {session_id}")
            del self.session_tasks[session_id]
        
        # End agent session
        asyncio.create_task(self.hw_agent.end_session(session_id))
    
    def is_connected(self, session_id: str) -> bool:
        """Check if a session is still connected."""
        return session_id in self.active_connections
    
    async def send_audio(self, session_id: str, audio_data: bytes):
        """Send audio data back to the frontend."""
        if not self.is_connected(session_id):
            logger.warning(f"Cannot send audio to disconnected session {session_id}")
            return
        
        try:
            # Encode audio data as base64 for WebSocket transmission
            b64_audio = base64.b64encode(audio_data).decode("utf-8")
            message = {
                "type": "audio",
                "data": b64_audio
            }
            
            websocket = self.active_connections[session_id]
            await websocket.send_text(json.dumps(message))
            
        except Exception as e:
            logger.error(f"Error sending audio to session {session_id}: {e}")
            self.disconnect(session_id)
    
    async def send_message(self, session_id: str, message_type: str, data: Dict = None):
        """Send a control message to the frontend."""
        if not self.is_connected(session_id):
            logger.warning(f"Cannot send message to disconnected session {session_id}")
            return
        
        try:
            message = {
                "type": message_type,
                "data": data or {}
            }
            
            websocket = self.active_connections[session_id]
            await websocket.send_text(json.dumps(message))
            
        except Exception as e:
            logger.error(f"Error sending message to session {session_id}: {e}")
            self.disconnect(session_id)
    
    async def handle_incoming_audio(self, session_id: str, audio_data: str):
        """Process incoming audio from the frontend."""
        try:
            # Decode base64 audio data
            audio_bytes = base64.b64decode(audio_data)
            
            # Send to the ADK Live agent
            await self.hw_agent.send_audio(session_id, audio_bytes)
            
        except Exception as e:
            logger.error(f"Error processing incoming audio for session {session_id}: {e}")
    
    async def handle_websocket_message(self, session_id: str, message: str):
        """Handle incoming WebSocket messages from the frontend."""
        try:
            data = json.loads(message)
            message_type = data.get("type")
            
            if message_type == "audio":
                # Handle incoming audio data
                audio_data = data.get("data", "")
                await self.handle_incoming_audio(session_id, audio_data)
                
            elif message_type == "start_recording":
                # Frontend started recording
                await self.send_message(session_id, "recording_started", {
                    "message": "Recording started, speak now!"
                })
                
            elif message_type == "stop_recording":
                # Frontend stopped recording
                await self.send_message(session_id, "recording_stopped", {
                    "message": "Processing your question..."
                })
                
            elif message_type == "ping":
                # Keep-alive ping
                await self.send_message(session_id, "pong", {})
                
            else:
                logger.warning(f"Unknown message type: {message_type}")
                
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON received from session {session_id}")
        except Exception as e:
            logger.error(f"Error handling WebSocket message: {e}")
    
    async def _start_agent_session(self, session_id: str):
        """Start the ADK Live agent session and handle events."""
        async def agent_session_handler():
            try:
                logger.info(f"Starting agent session for {session_id}")
                
                # Send initial status
                await self.send_message(session_id, "agent_ready", {
                    "message": "Ready to help with your homework!"
                })
                
                # Start the agent session and process events
                async for event in self.hw_agent.start_session(session_id):
                    await self._handle_agent_event(session_id, event)
                    
            except asyncio.CancelledError:
                logger.info(f"Agent session cancelled for {session_id}")
            except Exception as e:
                logger.error(f"Error in agent session for {session_id}: {e}")
                logger.error(traceback.format_exc())
                await self.send_message(session_id, "error", {
                    "message": f"Agent error: {str(e)}"
                })
        
        # Create and store the task
        task = asyncio.create_task(agent_session_handler())
        self.session_tasks[session_id] = task
    
    async def _handle_agent_event(self, session_id: str, event):
        """Handle events from the ADK Live agent."""
        try:
            # Handle audio content from agent
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if hasattr(part, 'inline_data') and part.inline_data:
                        # Send audio response back to frontend
                        await self.send_audio(session_id, part.inline_data.data)
                    
                    if hasattr(part, 'text') and part.text:
                        # Send text response (for debugging/transcription)
                        await self.send_message(session_id, "text", {
                            "content": part.text
                        })
            
            # Handle tool calls (image analysis requests)
            if hasattr(event, 'tool_call') and event.tool_call:
                await self.send_message(session_id, "tool_call", {
                    "tool": event.tool_call.name if hasattr(event.tool_call, 'name') else 'unknown',
                    "message": "I need to see your homework. Taking a picture..."
                })
            
            # Handle turn completion
            if hasattr(event, 'turn_complete') and event.turn_complete:
                await self.send_message(session_id, "turn_complete", {
                    "message": "Ready for your next question!"
                })
            
            # Handle interruption
            if hasattr(event, 'interrupted') and event.interrupted:
                await self.send_message(session_id, "interrupted", {
                    "message": "I was interrupted, go ahead!"
                })
            
            # Log event details for debugging
            event_str = str(event)
            if "partial=True" in event_str:
                logger.debug(f"Agent streaming event for {session_id}")
            
        except Exception as e:
            logger.error(f"Error handling agent event for {session_id}: {e}")


# Global manager instance
audio_websocket_manager = AudioWebSocketManager()


def get_audio_websocket_manager() -> AudioWebSocketManager:
    """Get the global audio WebSocket manager."""
    return audio_websocket_manager