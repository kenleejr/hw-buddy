"""
Tool execution and handling for HW Buddy WebSocket Server
"""

import logging
import asyncio
import time
import requests
import base64
from typing import Dict, Any
from firebase_admin import firestore

logger = logging.getLogger(__name__)

async def execute_tool(tool_name: str, params: Dict[str, Any], session_id: str, db: firestore.Client) -> Dict[str, Any]:
    """Execute a tool based on name and parameters"""
    try:
        if tool_name == "capture_image":
            return await capture_image_tool(params, session_id, db)
        else:
            logger.error(f"Unknown tool: {tool_name}")
            return {"error": f"Unknown tool: {tool_name}"}

    except Exception as e:
        logger.error(f"Error executing tool {tool_name}: {str(e)}")
        return {"error": f"Tool execution failed: {str(e)}"}

async def capture_image_tool(params: Dict[str, Any], session_id: str, db: firestore.Client) -> Dict[str, Any]:
    """
    Tool function that triggers mobile camera capture and returns image data
    """
    try:
        reason = params.get("reason", "To help with homework")
        logger.info(f"Capturing image for session {session_id}, reason: {reason}")
        
        # Get session reference
        session_ref = db.collection('sessions').document(session_id)
        
        # Get current command state to detect changes
        current_doc = session_ref.get()
        
        if not current_doc.exists:
            # Create the session document if it doesn't exist
            session_ref.set({
                'created_at': firestore.SERVER_TIMESTAMP,
                'status': 'active'
            })
        
        logger.info(f"Triggering camera capture for session {session_id}")
        
        # Send command to mobile app to take picture
        session_ref.update({
            'command': 'take_picture',
            'user_question': f"Camera triggered by AI: {reason}",
            'context': reason,
            'timestamp': firestore.SERVER_TIMESTAMP
        })
        
        # Wait for mobile app to upload image directly (polling approach)
        max_wait_time = 25  # seconds
        poll_interval = 0.5  # seconds
        start_time = time.time()
        
        while time.time() - start_time < max_wait_time:
            # Check if image has been uploaded directly
            session_doc = session_ref.get()
            if session_doc.exists:
                session_data = session_doc.to_dict()
                
                # Check if we have image data uploaded directly
                if session_data.get('command') == 'image_uploaded' and session_data.get('last_image_data'):
                    logger.info(f"Image uploaded directly for session {session_id}")
                    
                    image_base64 = session_data.get('last_image_data')
                    image_filename = session_data.get('last_image_filename', 'homework_image.jpg')
                    content_type = session_data.get('last_image_content_type', 'image/jpeg')
                    
                    logger.info(f"Image data retrieved, length: {len(image_base64)}")
                    
                    return {
                        "success": True,
                        "message": f"Image captured: {reason}",
                        "image_filename": image_filename,
                        "content_type": content_type,
                        "image_data": image_base64
                    }
            
            await asyncio.sleep(poll_interval)
        
        # Timeout - no image received
        logger.warning(f"Timeout waiting for image capture for session {session_id}")
        return {"error": "Timeout waiting for image capture from mobile device"}
            
    except Exception as e:
        logger.error(f"Error in capture_image_tool: {str(e)}")
        return {"error": f"Failed to capture image: {str(e)}"}