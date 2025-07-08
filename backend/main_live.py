"""
HW Buddy Backend with ADK Live Agent
Updated FastAPI server with ADK Live integration and audio streaming support.
"""

import asyncio
import logging
import os
import traceback
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import firebase_admin
from firebase_admin import credentials, firestore

# Import our new components
from hw_live_agent import get_hw_live_agent
from audio_websocket_server import get_audio_websocket_manager
from image_upload_handler import get_image_upload_handler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Firebase initialization is handled by hw_live_agent

# Create FastAPI app
app = FastAPI(
    title="HW Buddy Live Backend",
    version="2.0.0",
    description="Backend with ADK Live agent and audio streaming"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://127.0.0.1:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Get component instances
hw_agent = get_hw_live_agent()
websocket_manager = get_audio_websocket_manager(hw_agent)
image_handler = get_image_upload_handler(hw_agent, websocket_manager)


# Request/Response Models
class SessionCreateRequest(BaseModel):
    session_id: str


class SessionResponse(BaseModel):
    success: bool
    session_id: str
    message: str
    status: Optional[dict] = None


class ImageUploadResponse(BaseModel):
    success: bool
    session_id: str
    message: str
    analysis: Optional[dict] = None
    image_info: Optional[dict] = None


# Basic endpoints
@app.get("/")
async def root():
    """Root endpoint for health check."""
    return {
        "message": "HW Buddy Live Backend API",
        "version": "2.0.0",
        "features": ["ADK Live Agent", "Audio Streaming", "Direct Image Upload"]
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "agent_ready": True,
        "websocket_manager_ready": True,
        "image_handler_ready": True
    }


# Session management endpoints
@app.post("/sessions", response_model=SessionResponse)
async def create_session(request: SessionCreateRequest):
    """Create a new session."""
    try:
        session_id = request.session_id
        
        # Validate session ID
        if not image_handler.validate_session_id(session_id):
            raise HTTPException(status_code=400, detail="Invalid session ID format")
        
        # Create session in the agent
        session_data = await hw_agent.create_session(session_id)
        
        logger.info(f"Created session {session_id}")
        
        return SessionResponse(
            success=True,
            session_id=session_id,
            message="Session created successfully",
            status={
                "is_active": False,
                "has_image": False,
                "has_problem_state": False
            }
        )
        
    except Exception as e:
        logger.error(f"Error creating session {request.session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error creating session: {str(e)}")


@app.get("/sessions/{session_id}/status", response_model=SessionResponse)
async def get_session_status(session_id: str):
    """Get the status of a session."""
    try:
        status = hw_agent.get_session_status(session_id)
        
        if not status.get("exists"):
            raise HTTPException(status_code=404, detail="Session not found")
        
        return SessionResponse(
            success=True,
            session_id=session_id,
            message="Session status retrieved",
            status=status
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session status {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting session status: {str(e)}")


@app.delete("/sessions/{session_id}")
async def end_session(session_id: str):
    """End a session and clean up resources."""
    try:
        # End the agent session
        await hw_agent.end_session(session_id)
        
        # Disconnect WebSocket if connected
        websocket_manager.disconnect(session_id)
        
        logger.info(f"Ended session {session_id}")
        
        return {
            "success": True,
            "session_id": session_id,
            "message": "Session ended successfully"
        }
        
    except Exception as e:
        logger.error(f"Error ending session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error ending session: {str(e)}")


# Audio WebSocket endpoint
@app.websocket("/ws/audio/{session_id}")
async def audio_websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for bidirectional audio streaming."""
    try:
        # Validate session ID
        if not image_handler.validate_session_id(session_id):
            await websocket.close(code=1003, reason="Invalid session ID")
            return
        
        # Connect to WebSocket manager (this may reject the connection)
        connection_accepted = await websocket_manager.connect(websocket, session_id)
        
        # Only proceed if connection was accepted
        if connection_accepted:
            try:
                # Handle incoming messages
                while True:
                    message = await websocket.receive_text()
                    await websocket_manager.handle_websocket_message(session_id, message)
                    
            except WebSocketDisconnect:
                logger.info(f"Audio WebSocket disconnected for session {session_id}")
            except Exception as e:
                logger.error(f"Audio WebSocket error for session {session_id}: {e}")
                logger.error(traceback.format_exc())
        else:
            # Connection was rejected, just return
            return
        
    finally:
        websocket_manager.disconnect(session_id)


# Image upload endpoint
@app.post("/sessions/{session_id}/upload_image", response_model=ImageUploadResponse)
async def upload_image(
    session_id: str,
    file: UploadFile = File(...),
    user_ask: str = Form("")
):
    """Upload and process an image for homework analysis."""
    try:
        # Validate session ID
        if not image_handler.validate_session_id(session_id):
            raise HTTPException(status_code=400, detail="Invalid session ID format")
        
        # Process the image
        result = await image_handler.upload_and_process_image(
            session_id=session_id,
            file=file,
            user_ask=user_ask
        )
        
        return ImageUploadResponse(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading image for session {session_id}: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error processing image: {str(e)}")


@app.get("/sessions/{session_id}/image_status")
async def get_image_status(session_id: str):
    """Get the current image status for a session."""
    try:
        return await image_handler.get_session_image_status(session_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting image status for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting image status: {str(e)}")


# Legacy compatibility endpoint (for gradual migration)
@app.post("/take_picture")
async def take_picture_legacy(request: dict):
    """Legacy endpoint for backward compatibility during migration."""
    try:
        session_id = request.get("session_id")
        user_ask = request.get("user_ask", "Please help me with my homework")
        
        if not session_id:
            raise HTTPException(status_code=400, detail="session_id is required")
        
        # Check if session exists
        status = hw_agent.get_session_status(session_id)
        if not status.get("exists"):
            # Create session if it doesn't exist
            await hw_agent.create_session(session_id)
        
        # For legacy compatibility, we'll return a response indicating the request was received
        # The actual image processing will happen when the mobile app uploads the image
        return {
            "success": True,
            "message": "Image request received. Please upload image via mobile app.",
            "session_id": session_id,
            "image_url": None,
            "image_gcs_url": None,
            "image_description": "Waiting for image upload from mobile device..."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in legacy take_picture endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


# Development/debugging endpoints
@app.get("/debug/sessions")
async def debug_sessions():
    """Debug endpoint to list all active sessions."""
    try:
        sessions = []
        for session_id in hw_agent.sessions.keys():
            status = hw_agent.get_session_status(session_id)
            sessions.append({
                "session_id": session_id,
                "status": status
            })
        
        return {
            "active_sessions": len(sessions),
            "sessions": sessions,
            "websocket_connections": len(websocket_manager.active_connections)
        }
        
    except Exception as e:
        logger.error(f"Error in debug endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Debug error: {str(e)}")


# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize components on startup."""
    logger.info("Starting HW Buddy Live Backend...")
    logger.info("✅ ADK Live Agent initialized")
    logger.info("✅ Audio WebSocket manager initialized")
    logger.info("✅ Image upload handler initialized")
    logger.info("🚀 HW Buddy Live Backend ready!")


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on shutdown."""
    logger.info("Shutting down HW Buddy Live Backend...")
    
    # End all active sessions
    for session_id in list(hw_agent.sessions.keys()):
        try:
            await hw_agent.end_session(session_id)
            websocket_manager.disconnect(session_id)
        except Exception as e:
            logger.error(f"Error ending session {session_id} during shutdown: {e}")
    
    logger.info("✅ HW Buddy Live Backend shutdown complete")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main_live:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )