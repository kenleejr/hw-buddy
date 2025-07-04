"""
HW Buddy Live Agent using Google ADK Live API
This agent handles real-time audio streaming and image analysis for homework tutoring.
"""

import asyncio
import json
import logging
import base64
import io
from typing import Dict, Any, Optional, AsyncIterator
from PIL import Image

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

# Audio configuration matching frontend
RECEIVE_SAMPLE_RATE = 24000  # Audio output to frontend
SEND_SAMPLE_RATE = 16000     # Audio input from frontend
VOICE_NAME = "Aoede"         # Voice for responses

# Model configuration
MODEL = "gemini-2.0-flash-live-preview-04-09"

# System instruction for the homework tutor
SYSTEM_INSTRUCTION = """You are an AI homework tutor designed to help students with their assignments through voice interaction. 

When a student asks for help:
1. First, acknowledge their request warmly
2. ALWAYS call the take_picture_and_analyze tool to see their current work
3. Based on what you see, provide step-by-step guidance
4. Encourage the student and adapt your teaching style to their level

Key principles:
- Be patient and encouraging
- Break down complex problems into smaller steps
- Ask clarifying questions when needed
- Help students understand the "why" behind each step
- Use the student's visible work to provide contextual guidance

You have access to a camera that can see the student's homework. Use it wisely to understand their current progress and provide targeted help."""


class HWBuddyLiveAgent:
    """Live agent for homework tutoring with real-time audio and image processing."""
    
    def __init__(self):
        self.sessions: Dict[str, Any] = {}
        self.session_service = InMemorySessionService()
        
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
    
    def take_picture_and_analyze(self, user_ask: str) -> str:
        """
        Tool function to analyze the student's homework image.
        This will be called by the ADK agent when it needs visual context.
        
        Args:
            user_ask: The student's specific question or request
            
        Returns:
            JSON string with analysis results
        """
        # This function will be enhanced to work with the stored image data
        # For now, return a placeholder that the agent can work with
        return json.dumps({
            "status": "image_requested",
            "user_ask": user_ask,
            "message": "Taking picture of homework to analyze your current progress..."
        })
    
    async def create_session(self, session_id: str) -> Dict[str, Any]:
        """Create a new session for audio streaming."""
        if session_id in self.sessions:
            logger.warning(f"Session {session_id} already exists, returning existing session")
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
            
            # Convert image for analysis (you might want to add image preprocessing here)
            image = Image.open(io.BytesIO(image_data))
            
            # For now, we'll create a mock analysis
            # In a full implementation, you'd use the vision model here
            analysis_result = {
                "success": True,
                "problem_analysis": "Mathematical problem detected in the image",
                "student_progress": "Student has started working on the problem",
                "next_steps": "Continue with the next step in the solution",
                "mathjax_content": "$$\\text{Problem detected: } 2x + 3 = 7$$",
                "help_text": f"I can see your homework! {user_ask if user_ask else 'Let me help you with this problem.'}"
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