"""
HW Buddy Live Agent using Google ADK Live API
This agent handles real-time audio streaming and image analysis for homework tutoring.
"""

import asyncio
import json
import logging
import base64
import io
import os
import re
from typing import Dict, Any, Optional, AsyncIterator
from PIL import Image
import firebase_admin
from firebase_admin import credentials, firestore

# Google ADK imports
from google.adk.agents import Agent, LiveRequestQueue
from google.adk.runners import Runner
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.genai import types
from google import genai

# Local imports
from prompts import STATE_ESTABLISHER_AGENT_PROMPT, HINT_AGENT_PROMPT

# Configure logging
logger = logging.getLogger(__name__)

def extract_mathjax_content(text: str) -> str:
    """Extract MathJax content from Gemini response or return a basic format."""
    # Look for existing MathJax patterns
    math_patterns = [
        r'\$\$.*?\$\$',  # Display math
        r'\$.*?\$',      # Inline math
    ]
    
    found_math = []
    for pattern in math_patterns:
        matches = re.findall(pattern, text, re.DOTALL)
        found_math.extend(matches)
    
    if found_math:
        return '\n\n'.join(found_math)
    
    # If no explicit math found, try to extract equations or expressions
    # Look for common math patterns
    equation_patterns = [
        r'[a-zA-Z]?\s*[=]\s*.*',  # Equations with equals
        r'\d+[x]\s*[+\-]\s*\d+\s*[=]\s*\d+',  # Simple algebraic equations
    ]
    
    for pattern in equation_patterns:
        matches = re.findall(pattern, text)
        if matches:
            # Wrap in MathJax
            return '$$' + matches[0] + '$$'
    
    # Fallback: wrap the entire text as math if it looks mathematical
    if any(char in text for char in ['=', '+', '-', '*', '/', 'x', 'y']):
        return f"$${text.strip()}$$"
    
    return "$$\\text{Mathematical problem detected}$$"

# Audio configuration matching frontend
RECEIVE_SAMPLE_RATE = 24000  # Audio output to frontend
SEND_SAMPLE_RATE = 16000     # Audio input from frontend
VOICE_NAME = "Aoede"         # Voice for responses

# Model configuration
MODEL = "gemini-2.5-flash-preview-native-audio-dialog"

# System instruction for the homework tutor
SYSTEM_INSTRUCTION = """You are a helpful homework tutor. Be concise and wait for the student to ask for help first. 

When they ask for help with homework:
1. Acknowledge their request briefly
2. If they mention taking a picture or looking at their work, call the take_picture_and_analyze tool
3. Give clear, step-by-step guidance
4. Be encouraging but brief

Keep responses short and focused. Don't over-explain."""


class HWBuddyLiveAgent:
    """Live agent for homework tutoring with real-time audio and image processing."""
    
    def __init__(self):
        self.sessions: Dict[str, Any] = {}
        self.session_service = InMemorySessionService()
        
        # Initialize Firebase for Firestore communication
        self._init_firebase()
        
        # Create the ADK agent with homework tutoring capabilities
        self.agent = Agent(
            name="homework_tutor",
            model=MODEL,
            instruction=SYSTEM_INSTRUCTION,
            tools=[self.take_picture_and_analyze],
        )
        
        # Create runner for managing agent interactions
        self.runner = Runner(
            app_name="hw_buddy_live",
            agent=self.agent,
            session_service=self.session_service,
        )
        
        logger.info("HW Buddy Live Agent initialized")
    
    def _init_firebase(self):
        """Initialize Firebase connection for Firestore communication."""
        try:
            # Check if Firebase is already initialized
            firebase_admin.get_app()
            logger.info("Firebase already initialized")
        except ValueError:
            # Try multiple initialization methods
            initialized = False
            import os
            
            # Method 1: Try environment variable path (GOOGLE_APPLICATION_CREDENTIALS)
            if 'GOOGLE_APPLICATION_CREDENTIALS' in os.environ:
                service_account_path = os.environ['GOOGLE_APPLICATION_CREDENTIALS']
                # Handle relative paths
                if not os.path.isabs(service_account_path):
                    service_account_path = os.path.join(os.path.dirname(__file__), service_account_path)
                
                if os.path.exists(service_account_path):
                    try:
                        cred = credentials.Certificate(service_account_path)
                        firebase_admin.initialize_app(cred, {
                            'projectId': 'hw-buddy-66d6b'
                        })
                        logger.info(f"Firebase initialized with service account: {service_account_path}")
                        initialized = True
                    except Exception as e:
                        logger.warning(f"Service account initialization failed: {e}")
            
            # Method 2: Try default service account file location  
            if not initialized:
                service_account_path = os.path.join(os.path.dirname(__file__), "../donotinclude/hw-buddy-66d6b-firebase-adminsdk-fbsvc-78a283697a.json")
                if os.path.exists(service_account_path):
                    try:
                        cred = credentials.Certificate(service_account_path)
                        firebase_admin.initialize_app(cred, {
                            'projectId': 'hw-buddy-66d6b'
                        })
                        logger.info("Firebase initialized with donotinclude service account file")
                        initialized = True
                    except Exception as e:
                        logger.warning(f"Donotinclude service account initialization failed: {e}")
            
            # Method 3: Try application default credentials
            if not initialized:
                try:
                    os.environ['GOOGLE_CLOUD_PROJECT'] = 'hw-buddy-66d6b'
                    cred = credentials.ApplicationDefault()
                    firebase_admin.initialize_app(cred, {
                        'projectId': 'hw-buddy-66d6b'
                    })
                    logger.info("Firebase initialized with application default credentials")
                    initialized = True
                except Exception as e:
                    logger.warning(f"Application default credentials failed: {e}")
            
            if not initialized:
                logger.error("Could not initialize Firebase with any method")
                logger.error("Make sure GOOGLE_APPLICATION_CREDENTIALS points to the correct service account file")
                self.db = None
                return
        
        try:
            self.db = firestore.client()
            logger.info("Firestore client initialized successfully")
        except Exception as e:
            logger.warning(f"Could not initialize Firestore client: {e}")
            logger.info("Mobile app picture commands will not work")
            self.db = None
    
    def take_picture_and_analyze(self, user_ask: str) -> str:
        """
        Tool function to analyze the student's homework image.
        This will be called by the ADK agent when it needs visual context.
        
        Args:
            user_ask: The student's specific question or request
            
        Returns:
            JSON string with analysis results
        """
        logger.info(f"ADK agent requesting picture analysis: {user_ask}")
        
        # Get current session ID (we'll store this during session creation)
        current_session_id = getattr(self, 'current_session_id', None)
        if not current_session_id and self.sessions:
            # Fallback: get from sessions dict (should have one active)
            current_session_id = list(self.sessions.keys())[0]
        
        # Trigger mobile app to take picture via Firestore
        if self.db and current_session_id:
            try:
                self.db.collection('sessions').document(current_session_id).set({
                    'command': 'take_picture',
                    'user_ask': user_ask,
                    'timestamp': firestore.SERVER_TIMESTAMP,
                    'status': 'waiting_for_image'
                }, merge=True)
                logger.info(f"Firestore command sent to session {current_session_id}")
            except Exception as e:
                logger.error(f"Failed to send Firestore command: {e}")
        
        # Return response indicating we're waiting for the image
        return json.dumps({
            "status": "waiting_for_image",
            "user_ask": user_ask,
            "message": "I'm taking a picture of your homework now. Please wait a moment while I analyze it...",
            "session_id": current_session_id
        })
    
    async def create_session(self, session_id: str) -> Dict[str, Any]:
        """Create a new session for audio streaming."""
        if session_id in self.sessions:
            logger.warning(f"Session {session_id} already exists, returning existing session")
            self.current_session_id = session_id  # Track current session
            return self.sessions[session_id]
        
        # Create ADK session - this method is actually async!
        try:
            adk_session = await self.session_service.create_session(
                app_name="hw_buddy_live",
                user_id=f"student_{session_id}",
                session_id=session_id,
            )
            logger.info(f"ADK session created successfully for {session_id}")
        except Exception as e:
            logger.error(f"Failed to create ADK session for {session_id}: {e}")
            raise
        
        # Create live request queue for this session
        live_request_queue = LiveRequestQueue()
        
        # Create run config with audio settings
        run_config = RunConfig(
            streaming_mode=StreamingMode.BIDI,
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=VOICE_NAME
                    )
                )
            ),
            response_modalities=["AUDIO"],
            output_audio_transcription=types.AudioTranscriptionConfig(),
            input_audio_transcription=types.AudioTranscriptionConfig(),
        )
        
        # Store session data
        session_data = {
            "session_id": session_id,
            "adk_session": adk_session,
            "live_request_queue": live_request_queue,
            "run_config": run_config,
            "current_image": None,
            "problem_state": None,
            "is_active": False,
        }
        
        self.sessions[session_id] = session_data
        self.current_session_id = session_id  # Track current session
        logger.info(f"Created session {session_id}")
        
        return session_data
    
    async def start_session(self, session_id: str) -> AsyncIterator[Any]:
        """Start the ADK Live session and return the event stream."""
        session_data = self.sessions.get(session_id)
        if not session_data:
            raise ValueError(f"Session {session_id} not found")
        
        session_data["is_active"] = True
        logger.info(f"Starting ADK Live session {session_id}")
        
        # Start the live session with the runner
        async for event in self.runner.run_live(
            session=session_data["adk_session"],
            live_request_queue=session_data["live_request_queue"],
            run_config=session_data["run_config"],
        ):
            yield event
    
    async def send_audio(self, session_id: str, audio_data: bytes):
        """Send audio data to the ADK Live session."""
        session_data = self.sessions.get(session_id)
        if not session_data or not session_data["is_active"]:
            logger.warning(f"Session {session_id} not active, ignoring audio")
            return
        
        # Send audio to the live request queue
        session_data["live_request_queue"].send_realtime(
            types.Blob(
                data=audio_data,
                mime_type=f"audio/pcm;rate={SEND_SAMPLE_RATE}",
            )
        )
    
    async def process_image(self, session_id: str, image_data: bytes, user_ask: str = "") -> Dict[str, Any]:
        """
        Process an uploaded image for homework analysis.
        
        Args:
            session_id: The session ID
            image_data: Raw image bytes
            user_ask: The student's question about the image
            
        Returns:
            Analysis results as a dictionary
        """
        session_data = self.sessions.get(session_id)
        if not session_data:
            raise ValueError(f"Session {session_id} not found")
        
        try:
            # Store the image in the session
            session_data["current_image"] = image_data
            
            # Convert image for analysis
            image = Image.open(io.BytesIO(image_data))
            logger.info(f"Processing image: {image.size}, format: {image.format}")
            
            # Real Gemini image analysis
            try:
                # Create client and content for Gemini
                client = genai.Client(
                    api_key=os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
                )
                
                # Create analysis prompt based on user question
                analysis_prompt = f"""
                Analyze this homework image and extract the mathematical problem and any student work shown.
                
                User's question: "{user_ask if user_ask else 'Help me with this problem'}"
                
                Provide the response in this exact format:
                
                **Problem:** [Brief description of the main problem]
                
                $$[main_equation_or_problem]$$
                
                **Student's Work:**
                $$[any_work_shown]$$
                
                **Current Status:** [What step they're on or what needs to be done next]
                
                Focus on mathematical content and format equations properly in LaTeX/MathJax notation.
                """
                
                # Create content with image and text
                contents = [
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_bytes(
                                mime_type="image/jpeg",
                                data=image_data
                            ),
                            types.Part.from_text(text=analysis_prompt),
                        ],
                    ),
                ]
                
                # Generate content config
                generate_content_config = types.GenerateContentConfig(
                    response_mime_type="text/plain",
                )
                
                # Generate analysis
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=contents,
                    config=generate_content_config,
                )
                
                if response and response.text:
                    analysis_text = response.text
                    logger.info(f"Gemini analysis: {analysis_text[:200]}...")
                    
                    # Extract MathJax content from the response
                    mathjax_content = extract_mathjax_content(analysis_text)
                    
                    analysis_result = {
                        "success": True,
                        "problem_analysis": analysis_text,
                        "student_progress": "Analyzing student's current work...",
                        "next_steps": "Based on the image analysis",
                        "mathjax_content": mathjax_content,
                        "help_text": f"I can see your homework! {analysis_text}"
                    }
                else:
                    # Fallback if no response
                    raise Exception("No response from Gemini model")
                    
            except Exception as gemini_error:
                logger.error(f"Gemini analysis failed: {gemini_error}")
                # Fallback to basic analysis
                analysis_result = {
                    "success": True,
                    "problem_analysis": "I can see your homework image but had trouble with detailed analysis.",
                    "student_progress": "Image received successfully",
                    "next_steps": "Let me help you work through this step by step",
                    "mathjax_content": "$$\\text{Problem detected in image}$$",
                    "help_text": f"I can see your homework! {user_ask if user_ask else 'Let me help you with this problem.'} (Note: Using basic analysis due to processing issue)"
                }
            
            # Update problem state
            session_data["problem_state"] = analysis_result
            
            logger.info(f"Processed image for session {session_id}")
            return analysis_result
            
        except Exception as e:
            logger.error(f"Error processing image for session {session_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "help_text": "I'm having trouble analyzing the image. Could you try taking another picture?"
            }
    
    async def end_session(self, session_id: str):
        """End a session and clean up resources."""
        if session_id in self.sessions:
            self.sessions[session_id]["is_active"] = False
            del self.sessions[session_id]
            logger.info(f"Ended session {session_id}")
    
    def get_session_status(self, session_id: str) -> Dict[str, Any]:
        """Get the current status of a session."""
        session_data = self.sessions.get(session_id)
        if not session_data:
            return {"exists": False}
        
        return {
            "exists": True,
            "is_active": session_data["is_active"],
            "has_image": session_data["current_image"] is not None,
            "has_problem_state": session_data["problem_state"] is not None,
        }


# Global instance
hw_live_agent = HWBuddyLiveAgent()


def get_hw_live_agent() -> HWBuddyLiveAgent:
    """Get the global homework live agent instance."""
    return hw_live_agent