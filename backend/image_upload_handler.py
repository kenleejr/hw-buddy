"""
Image Upload Handler for HW Buddy
Handles direct image uploads from mobile app and processes them for homework analysis.
"""

import logging
import io
from typing import Dict, Any, Optional
from fastapi import UploadFile, HTTPException
from PIL import Image
from hw_live_agent import get_hw_live_agent
from audio_websocket_server import get_audio_websocket_manager

logger = logging.getLogger(__name__)


class ImageUploadHandler:
    """Handles image uploads and processing for homework analysis."""
    
    def __init__(self, hw_agent=None, websocket_manager=None):
        self.hw_agent = hw_agent or get_hw_live_agent()
        self.websocket_manager = websocket_manager or get_audio_websocket_manager()
        
        # Supported image formats
        self.supported_formats = {'image/jpeg', 'image/jpg', 'image/png', 'image/webp'}
        
        # Max image size (10MB)
        self.max_size = 10 * 1024 * 1024
    
    async def upload_and_process_image(
        self, 
        session_id: str, 
        file: UploadFile, 
        user_ask: str = ""
    ) -> Dict[str, Any]:
        """
        Handle image upload from mobile app and process it.
        
        Args:
            session_id: The session ID
            file: The uploaded image file
            user_ask: Optional user question about the image
            
        Returns:
            Processing results as a dictionary
        """
        try:
            logger.info(f"Processing image upload for session {session_id}")
            logger.info(f"File info: filename={file.filename}, content_type={file.content_type}")
            
            # Validate session exists
            session_status = self.hw_agent.get_session_status(session_id)
            if not session_status.get("exists"):
                logger.error(f"Session {session_id} not found")
                raise HTTPException(
                    status_code=404, 
                    detail=f"Session {session_id} not found"
                )
            
            # Validate file type
            if file.content_type not in self.supported_formats:
                logger.error(f"Unsupported file type: {file.content_type}. Supported: {self.supported_formats}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported file type: {file.content_type}. "
                           f"Supported types: {', '.join(self.supported_formats)}"
                )
            
            # Read and validate file size
            image_data = await file.read()
            if len(image_data) > self.max_size:
                raise HTTPException(
                    status_code=400,
                    detail=f"File too large. Max size: {self.max_size // (1024*1024)}MB"
                )
            
            # Validate image can be opened
            try:
                image = Image.open(io.BytesIO(image_data))
                image.verify()  # Verify the image is valid
                logger.info(f"Image uploaded for session {session_id}: "
                           f"{image.format} {image.size} ({len(image_data)} bytes)")
            except Exception as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid image file: {str(e)}"
                )
            
            # Notify frontend that image was received
            if self.websocket_manager.is_connected(session_id):
                await self.websocket_manager.send_message(session_id, "image_received", {
                    "message": "Image received, analyzing your homework...",
                    "image_info": {
                        "format": image.format,
                        "size": image.size,
                        "file_size": len(image_data)
                    }
                })
            
            # Store the image with the agent (expert help agent handles analysis)
            store_result = await self.hw_agent.store_uploaded_image(
                session_id=session_id,
                image_data=image_data,
                mime_type=file.content_type or "image/jpeg"
            )
            
            # Create simple response - analysis is handled by expert help agent
            analysis_result = {
                "success": store_result["success"],
                "problem_analysis": "Image stored successfully. Expert help agent will analyze it.",
                "student_progress": "Image uploaded successfully",
                "next_steps": "The expert help agent will handle detailed analysis",
                "mathjax_content": "$$\\text{Image uploaded}$$",
                "help_text": "Image uploaded successfully. The expert help agent will analyze it."
            }
            
            # Prepare response
            response = {
                "success": True,
                "session_id": session_id,
                "message": "Image processed successfully",
                "analysis": analysis_result,
                "image_info": {
                    "format": image.format,
                    "size": list(image.size),
                    "file_size": len(image_data)
                }
            }
            
            logger.info(f"Successfully processed image for session {session_id}")
            return response
            
        except HTTPException:
            # Re-raise HTTP exceptions as-is
            raise
        except Exception as e:
            logger.error(f"Error processing image upload for session {session_id}: {e}")
            
            # Notify frontend of error if connected
            if self.websocket_manager.is_connected(session_id):
                await self.websocket_manager.send_message(session_id, "image_error", {
                    "message": f"Error processing image: {str(e)}"
                })
            
            raise HTTPException(
                status_code=500,
                detail=f"Error processing image: {str(e)}"
            )
    
    async def get_session_image_status(self, session_id: str) -> Dict[str, Any]:
        """
        Get the current image status for a session.
        
        Args:
            session_id: The session ID
            
        Returns:
            Status information about images in the session
        """
        try:
            session_status = self.hw_agent.get_session_status(session_id)
            
            if not session_status.get("exists"):
                raise HTTPException(
                    status_code=404,
                    detail=f"Session {session_id} not found"
                )
            
            return {
                "session_id": session_id,
                "has_image": session_status.get("has_image", False),
                "has_problem_state": session_status.get("has_problem_state", False),
                "is_active": session_status.get("is_active", False)
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting image status for session {session_id}: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Error getting session status: {str(e)}"
            )
    
    def validate_session_id(self, session_id: str) -> bool:
        """
        Validate that a session ID is properly formatted.
        
        Args:
            session_id: The session ID to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not session_id or not isinstance(session_id, str):
            return False
        
        # Basic validation - you might want to add more specific rules
        if len(session_id) < 5 or len(session_id) > 100:
            return False
        
        # Check for valid characters (alphanumeric, underscore, hyphen)
        import re
        if not re.match(r'^[a-zA-Z0-9_-]+$', session_id):
            return False
        
        return True


# Global handler instance
image_upload_handler = None


def get_image_upload_handler(hw_agent=None, websocket_manager=None) -> ImageUploadHandler:
    """Get the global image upload handler."""
    global image_upload_handler
    if image_upload_handler is None:
        image_upload_handler = ImageUploadHandler(hw_agent, websocket_manager)
    return image_upload_handler