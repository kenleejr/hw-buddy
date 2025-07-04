"""
Configuration for HW Buddy WebSocket Server
"""

import os
import logging
from typing import Dict, Optional
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load environment variables from root project directory
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

class ConfigurationError(Exception):
    """Custom exception for configuration errors."""
    pass

class ApiConfig:
    """API configuration handler."""
    
    def __init__(self):
        # Determine if using Vertex AI
        self.use_vertex = os.getenv('VERTEX_API', 'false').lower() == 'true'
        
        self.api_key: Optional[str] = None
        
        logger.info(f"Initialized API configuration with Vertex AI: {self.use_vertex}")
    
    async def initialize(self):
        """Initialize API credentials."""
        if not self.use_vertex:
            # Try both GOOGLE_API_KEY and GEMINI_API_KEY for compatibility
            self.api_key = os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY')
            if not self.api_key:
                raise ConfigurationError("No Google API key available from environment (GOOGLE_API_KEY or GEMINI_API_KEY)")

# Initialize API configuration
api_config = ApiConfig()

# Model configuration
if api_config.use_vertex:
    MODEL = os.getenv('MODEL_VERTEX_API', 'gemini-2.0-flash-exp')
    VOICE = os.getenv('VOICE_VERTEX_API', 'Aoede')
else:
    MODEL = os.getenv('MODEL_DEV_API', 'models/gemini-2.0-flash-exp')
    VOICE = os.getenv('VOICE_DEV_API', 'Puck')

logger.info(f"Using model: {MODEL}, voice: {VOICE}")

# Load system instructions for homework tutoring
SYSTEM_INSTRUCTIONS = """You are an intelligent homework tutor assistant that helps students with their homework. 
You have access to an overhead camera that can see the student's workspace and homework materials.

When helping students:
1. Use the image capture tool to see their work when needed
2. Provide step-by-step guidance, not just answers
3. Encourage learning by asking follow-up questions
4. Be encouraging and supportive
5. Format mathematical expressions clearly
6. Explain concepts in an age-appropriate way

You have access to a tool called 'capture_image' that takes a photo of the student's workspace.
Use this tool when you need to see what the student is working on to provide better assistance."""

# Gemini Configuration
CONFIG = {
    "generation_config": {
        "response_modalities": ["AUDIO"],
        "speech_config": VOICE
    },
    "tools": [{
        "function_declarations": [
            {
                "name": "capture_image",
                "description": "Capture an image of the student's workspace to see their homework",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "reason": {
                            "type": "string", 
                            "description": "Why you need to see the student's work (e.g., 'to help with math problem', 'to check progress')"
                        }
                    },
                    "required": ["reason"]
                }
            }
        ]
    }],
    "system_instruction": SYSTEM_INSTRUCTIONS
}