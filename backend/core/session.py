"""
Session management for HW Buddy WebSocket Server
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional
import asyncio

@dataclass
class SessionState:
    """Tracks the state of a client session"""
    is_receiving_response: bool = False
    interrupted: bool = False
    current_tool_execution: Optional[asyncio.Task] = None
    current_audio_stream: Optional[Any] = None
    genai_session: Optional[Any] = None
    received_model_response: bool = False
    session_id: str = ""  # Store the session ID for Firestore operations
    
    # HW Buddy specific state
    last_image_url: Optional[str] = None
    last_image_gcs_url: Optional[str] = None
    is_mobile_client: bool = False  # Track if this is a mobile client (camera)
    is_web_client: bool = False     # Track if this is a web client (interface)

# Global session storage
active_sessions: Dict[str, SessionState] = {}

def create_session(session_id: str) -> SessionState:
    """Create and store a new session"""
    session = SessionState()
    session.session_id = session_id
    active_sessions[session_id] = session
    return session

def get_session(session_id: str) -> Optional[SessionState]:
    """Get an existing session"""
    return active_sessions.get(session_id)

def remove_session(session_id: str) -> None:
    """Remove a session"""
    if session_id in active_sessions:
        del active_sessions[session_id]

def update_session_image(session_id: str, image_url: str, image_gcs_url: str = None) -> None:
    """Update session with new image URLs"""
    session = get_session(session_id)
    if session:
        session.last_image_url = image_url
        session.last_image_gcs_url = image_gcs_url