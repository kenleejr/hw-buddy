"""
HW Buddy Live Agent using Google ADK Live API
This agent handles real-time audio streaming and image analysis for homework tutoring.
"""

import asyncio
import logging
import traceback
import re
import json
from typing import Dict, Any, Optional, AsyncIterator
from PIL import Image
import firebase_admin
from firebase_admin import credentials, firestore

# Google ADK imports
from google.adk.agents import Agent, LiveRequestQueue
from google.adk.runners import Runner
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.adk.tools.agent_tool import AgentTool
from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.tools import FunctionTool, ToolContext
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from google.genai import types
from google.genai.types import Part, UserContent, Content
from google import genai

# Local imports
from prompts import STATE_ESTABLISHER_AGENT_PROMPT, HINT_AGENT_PROMPT

# Configure logging
logger = logging.getLogger(__name__)

def escape_mathjax_backslashes(text: str) -> str:
    """
    Escape backslashes in MathJax expressions for valid JSON.
    """
    # Pattern to match MathJax expressions (both $...$ and $$...$$)
    # We need to escape backslashes within these expressions
    def escape_in_math(match):
        content = match.group(0)
        # Double escape backslashes for JSON
        return content.replace('\\', '\\\\')
    
    # Match both inline and display math
    text = re.sub(r'\$\$[^$]*\$\$', escape_in_math, text)
    text = re.sub(r'\$[^$]*\$', escape_in_math, text)
    
    return text

def fix_malformed_json(json_str: str) -> str:
    """
    Attempt to fix common JSON formatting issues like unescaped newlines and quotes.
    """
    # Fix unescaped newlines in JSON string values
    # This is a simple regex approach that handles the most common cases
    import re
    
    # Pattern to find content inside double quotes that contains unescaped newlines
    def escape_newlines_in_values(match):
        content = match.group(1)
        # Escape newlines and other control characters
        content = content.replace('\n', '\\n')
        content = content.replace('\r', '\\r')
        content = content.replace('\t', '\\t')
        content = content.replace('\b', '\\b')
        content = content.replace('\f', '\\f')
        return f'"{content}"'
    
    # Find and fix string values with unescaped characters
    # Pattern matches: "key": "value with potential newlines"
    pattern = r'"([^"]*(?:\n|\r|\t|\b|\f)[^"]*)"'
    fixed_json = re.sub(pattern, escape_newlines_in_values, json_str)
    
    return fixed_json

def clean_agent_response(response_text: str) -> str:
    """
    Clean the agent response by removing common markdown formatting.
    Removes ```json prefix and ``` suffix that LLMs often add.
    Also ensures proper JSON formatting by re-encoding if needed.
    """
    if not response_text:
        return response_text
    
    # Remove ```json at the beginning (case insensitive)
    cleaned = re.sub(r'^```json\s*', '', response_text, flags=re.IGNORECASE)
    
    # Remove ``` at the beginning if it's still there
    cleaned = re.sub(r'^```\s*', '', cleaned)
    
    # Remove ``` at the end
    cleaned = re.sub(r'\s*```$', '', cleaned)
    
    cleaned = cleaned.strip()
    
    # Escape backslashes in MathJax expressions for valid JSON
    cleaned = escape_mathjax_backslashes(cleaned)
    
    # Try to parse and re-encode as JSON to fix any formatting issues
    try:
        # If it's valid JSON, parse and re-encode to ensure proper escaping
        parsed = json.loads(cleaned)
        # Re-encode with proper escaping
        cleaned = json.dumps(parsed, ensure_ascii=False)
        logger.info("Successfully re-encoded agent response as proper JSON")
    except json.JSONDecodeError as e:
        logger.warning(f"Agent response has malformed JSON, attempting to fix: {e}")
        # Try to fix common JSON issues like unescaped newlines and quotes
        try:
            fixed_json = fix_malformed_json(cleaned)
            parsed = json.loads(fixed_json)
            cleaned = json.dumps(parsed, ensure_ascii=False)
            logger.info("Successfully fixed and re-encoded malformed JSON")
        except Exception as fix_error:
            logger.error(f"Could not fix malformed JSON: {fix_error}")
            # Return the cleaned text as-is if we can't fix it
    
    return cleaned

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
MODEL = "gemini-live-2.5-flash-preview-native-audio"

# System instruction for the homework tutor
SYSTEM_INSTRUCTION = """You are a homework buddy assistant. \
              When a user asks you anything, first respond with affirmative that you can help and then in order to help them you must call the get_expert_help function. \
              Pass the user's specific question or request as the 'user_ask' parameter to the get_expert_help function. \
              This function will analyze the student's progress and provide next steps specifically tailored to the user's request. Note: this can take some time. While waiting do not say anything. \
              Do NOT supply help outside of the results of this function's result. \
              When a response returns, simply relay the function's response to the user, as it contains pointers to the student."""


class HWBuddyLiveAgent:
    """Live agent for homework tutoring with real-time audio and image processing."""
    
    def __init__(self):
        self.sessions: Dict[str, Any] = {}
        self.session_service = InMemorySessionService()
        self.expert_session_service = InMemorySessionService()
        
        # Event coordination for image uploads
        self.upload_events: Dict[str, asyncio.Event] = {}
        self.session_images: Dict[str, Dict[str, Any]] = {}
        
        
        # Initialize Firebase for Firestore communication
        self._init_firebase()
        
        # Define dummy before_model_callback for testing
        def dummy_before_model_callback(callback_context, llm_request):
            """
            Dummy callback that logs when it's triggered to test callback functionality.
            """
            logger.info("🔥 BEFORE_MODEL_CALLBACK TRIGGERED!")
            logger.info(f"🔥 Callback context state: {callback_context.state}")
            logger.info(f"🔥 LLM request contents length: {len(llm_request.contents) if llm_request.contents else 0}")
            if llm_request.contents:
                for i, content in enumerate(llm_request.contents):
                    logger.info(f"🔥 Content {i}: role={content.role}, parts={len(content.parts) if content.parts else 0}")
        
        # Create the expert help agent (based on hw_tutor_agent.py)
        self.expert_help_agent = self._create_expert_help_agent()
        
        # Create the expert help runner (independent from main live agent)
        self.expert_help_runner = Runner(
            app_name="expert_help",
            agent=self.expert_help_agent,
            session_service=self.expert_session_service,
        )
        
        # Create the get_expert_help function tool
        self.get_expert_help_tool = FunctionTool(
            func=self._create_get_expert_help_function()
        )
        
        # Create the ADK agent with homework tutoring capabilities
        self.agent = Agent(
            name="homework_tutor",
            model=MODEL,
            instruction=SYSTEM_INSTRUCTION,
            tools=[self.get_expert_help_tool],
            before_model_callback=dummy_before_model_callback,
        )
        
        # Create runner for managing agent interactions
        self.runner = Runner(
            app_name="hw_buddy_live",
            agent=self.agent,
            session_service=self.session_service,
        )
        
        logger.info("HW Buddy Live Agent initialized")
    
    def _create_expert_help_agent(self) -> SequentialAgent:
        """Create the expert help agent based on hw_tutor_agent.py logic."""
        from prompts import STATE_ESTABLISHER_AGENT_PROMPT, HINT_AGENT_PROMPT
        
        # Create the take_picture tool function
        def create_take_picture_function(agent_instance):
            async def take_picture_and_analyze_tool(tool_context: ToolContext, user_ask: str) -> str:
                """
                Tool that triggers image capture and retrieves raw image bytes.
                The image bytes are stored in context for injection into the next LLM request.
                """
                try:
                    # Get current session ID from the live agent
                    current_session_id = getattr(agent_instance, 'current_session_id', None)
                    if not current_session_id and agent_instance.sessions:
                        current_session_id = list(agent_instance.sessions.keys())[0]
                    
                    if not current_session_id:
                        logger.error("No session_id found in tool context state")
                        raise Exception("No session_id found in context")
                    
                    logger.info(f"Taking picture for session {current_session_id}, user_ask: {user_ask}")
                    
                    # Create event and register it for direct notification
                    upload_event = asyncio.Event()
                    agent_instance.upload_events[current_session_id] = upload_event
                    
                    # Trigger picture taking via Firestore
                    if agent_instance.db:
                        session_ref = agent_instance.db.collection('sessions').document(current_session_id)
                        session_ref.update({'command': 'take_picture'})
                        logger.info(f"Sent take_picture command to session {current_session_id}")
                    
                    # Wait for direct notification from upload endpoint
                    try:
                        await asyncio.wait_for(upload_event.wait(), timeout=30)
                        logger.info(f"Received upload notification for session {current_session_id}")
                    except asyncio.TimeoutError:
                        raise Exception(f"Timeout waiting for image upload from session {current_session_id}")
                    finally:
                        # Clean up event to prevent memory leaks
                        if current_session_id in agent_instance.upload_events:
                            del agent_instance.upload_events[current_session_id]
                    
                    # Get raw image bytes from session storage
                    if current_session_id not in agent_instance.session_images:
                        raise Exception(f"No image data found for session {current_session_id}")
                    
                    image_data = agent_instance.session_images[current_session_id]
                    image_bytes = image_data['bytes']
                    mime_type = image_data['mime_type']
                    
                    logger.info(f"Retrieved image data: {len(image_bytes)} bytes, type: {mime_type}")
                    
                    # Store image bytes in context for injection callback
                    tool_context.state["pending_image_bytes"] = image_bytes
                    tool_context.state["pending_image_mime_type"] = mime_type
                    tool_context.state["pending_user_ask"] = user_ask
                    
                    # Clean up session image storage
                    del agent_instance.session_images[current_session_id]
                    
                    return "Image captured successfully. I can now see your homework."
                    
                except Exception as e:
                    logger.error(f"Error in take_picture_and_analyze_tool: {str(e)}")
                    return f"Error capturing image: {str(e)}"
            
            return take_picture_and_analyze_tool
        
        # Create the injection callback
        def inject_image_callback(callback_context: CallbackContext, llm_request: LlmRequest):
            """
            Before model callback that injects pending image bytes into the LLM request.
            """
            pending_image_bytes = callback_context.state.get("pending_image_bytes")
            pending_mime_type = callback_context.state.get("pending_image_mime_type", "image/jpeg")
            
            if pending_image_bytes:
                logger.info(f"Injecting image bytes into LLM request: {len(pending_image_bytes)} bytes, type: {pending_mime_type}")
                
                # Create image part from raw bytes
                image_part = Part.from_bytes(
                    data=pending_image_bytes,
                    mime_type=pending_mime_type
                )
                
                # Add the image content to the LLM request
                if not llm_request.contents:
                    llm_request.contents = []
                
                # Insert the image content as a user message
                image_content = Content(role="user", parts=[image_part])
                llm_request.contents.append(image_content)
                
                # Clear the pending image from state to avoid reinjection
                callback_context.state["pending_image_bytes"] = None
                callback_context.state["pending_image_mime_type"] = None
                
                logger.info("Image bytes successfully injected into LLM request")
        
        # Create the take picture tool
        take_picture_tool = FunctionTool(
            func=create_take_picture_function(self)
        )
        
        # Create the hint agent
        hint_agent = LlmAgent(
            name="HintAgent",
            model="gemini-2.5-flash",
            instruction=HINT_AGENT_PROMPT
        )
        
        # Create the state establisher agent
        state_establisher_agent = LlmAgent(
            name="StateEstablisher",
            model="gemini-2.5-flash",
            tools=[take_picture_tool],
            before_model_callback=inject_image_callback,
            output_key="problem_at_hand",
            instruction=STATE_ESTABLISHER_AGENT_PROMPT
        )
        
        # Create before agent callback
        async def before_agent_callback1(callback_context: CallbackContext) -> Optional[Content]:
            user_interaction_count = callback_context.state.get("user_interaction_count", 0)
            if user_interaction_count == 0:
                callback_context.state["problem_at_hand"] = "None"
            elif callback_context.state.get("problem_at_hand", None):
                callback_context.state["problem_at_hand"] = "None"
            callback_context.state["user_interaction_count"] = user_interaction_count + 1
            return None
        
        # Create the sequential agent
        expert_agent = SequentialAgent(
            name="expert_help_agent",
            before_agent_callback=[before_agent_callback1],
            sub_agents=[state_establisher_agent, hint_agent]
        )
        
        return expert_agent
    
    def _create_get_expert_help_function(self):
        """Create the get_expert_help function that uses the independent runner."""
        async def get_expert_help(tool_context: ToolContext, user_ask: str) -> str:
            """
            Get expert help by running the independent expert help agent.
            This function creates its own session and event loop, emitting events that
            will be forwarded to the frontend for processing status updates.
            """
            try:
                # Get current session ID for event forwarding
                current_session_id = getattr(self, 'current_session_id', None)
                if not current_session_id and self.sessions:
                    current_session_id = list(self.sessions.keys())[0]
                
                if not current_session_id:
                    logger.error("No session_id found for expert help")
                    return "I apologize, but I couldn't access the session to help you."
                
                # Get the session data including expert session
                session_data = self.sessions.get(current_session_id)
                if not session_data:
                    logger.error(f"Session data not found for {current_session_id}")
                    return "I apologize, but I couldn't access the session data."
                
                expert_session = session_data.get("expert_session")
                if not expert_session:
                    logger.error(f"Expert session not found for {current_session_id}")
                    return "I apologize, but I couldn't access the expert session."
                
                logger.info(f"Starting expert help for session {current_session_id}, user_ask: {user_ask}")
                
                # Set up event forwarding callback
                async def forward_events(session_id, event):
                    """Forward expert help events to the main session."""
                    from audio_websocket_server import get_audio_websocket_manager
                    websocket_manager = get_audio_websocket_manager()
                    if websocket_manager:
                        # Forward the event to the main session
                        await websocket_manager._send_adk_event_update(current_session_id, event)
                
                # Run the expert help agent with event forwarding
                final_response = ""
                final_response_data = None
                # Create run config
                run_config = RunConfig(
                    streaming_mode=StreamingMode.NONE,
                    max_llm_calls=10
                )
                
                # Run the agent using the actual session ID from the created/retrieved session
                content = UserContent(parts=[Part(text=user_ask)])
                logger.info(expert_session)
                async for event in self.expert_help_runner.run_async(
                    session_id=expert_session.id,
                    new_message=content,
                    run_config=run_config,
                    user_id="student"
                ):
                    # Forward events to the main session for frontend updates
                    await forward_events(current_session_id, event)
                    
                    # Check if this is a final response but don't return yet - collect it
                    if event.is_final_response() and not final_response_data and event.author == "root_agent":
                        logger.info("Found final response event!")
                        # Extract text content
                        if event.content:
                            for part in event.content.parts:
                                logger.info(f"Checking part: {part}")
                                if hasattr(part, 'text') and part.text:
                                    logger.info(f"🔍 Expert help agent final output: {part.text}")
                                    
                                    # Store the response text (cleaning now happens in event forwarding)
                                    final_response_data = {
                                        "response": part.text
                                    }
                
                # Return the final response if we found one
                if final_response_data:
                    raw_response = final_response_data["response"]
                    
                    # Clean the response and extract help_text for the live agent to recite
                    cleaned_response = clean_agent_response(raw_response)
                    logger.info(f"🔍 Cleaned expert help response: {cleaned_response}")
                    
                    # Try to parse as JSON and extract help_text
                    try:
                        parsed_response = json.loads(cleaned_response)
                        if isinstance(parsed_response, dict) and "help_text" in parsed_response:
                            final_response = parsed_response["help_text"]
                            logger.info(f"🔍 Extracted help_text for live agent: {final_response}")
                        else:
                            # Fallback to cleaned response if no help_text found
                            final_response = cleaned_response
                            logger.info("🔍 No help_text found, using cleaned response")
                    except json.JSONDecodeError:
                        # Fallback to cleaned response if not valid JSON
                        final_response = cleaned_response
                        logger.info("🔍 Response not valid JSON, using cleaned response")
                
                logger.info(f"Expert help completed for session {current_session_id}")
                return final_response or "I've analyzed your homework and provided guidance above."
                
            except Exception as e:
                logger.error(f"Error in get_expert_help: {str(e)}")
                return f"I apologize, but I encountered an error while analyzing your homework: {str(e)}"
        
        return get_expert_help
    
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
                            'projectId': os.environ["GOOGLE_CLOUD_PROJECT"]
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
                            'projectId': os.environ["GOOGLE_CLOUD_PROJECT"]
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
                        'projectId': os.environ["GOOGLE_CLOUD_PROJECT"]
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
        
        # Create expert session for this live session
        expert_session = await self.expert_session_service.create_session(
            app_name="expert_help",
            user_id="student",
            session_id=f"expert_{session_id}",
        )
        
        # Store session data
        session_data = {
            "session_id": session_id,
            "adk_session": adk_session,
            "expert_session": expert_session,
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
    
    async def store_uploaded_image(self, session_id: str, image_data: bytes, mime_type: str) -> Dict[str, Any]:
        """
        Store an uploaded image and notify waiting tools.
        This is called by the image upload handler when an image is received.
        
        Args:
            session_id: The session ID
            image_data: Raw image bytes
            mime_type: MIME type of the image
            
        Returns:
            Storage confirmation
        """
        try:
            # Store image data
            self.session_images[session_id] = {
                'bytes': image_data,
                'mime_type': mime_type
            }
            
            logger.info(f"Stored image for session {session_id}: {len(image_data)} bytes, type: {mime_type}")
            
            # Notify waiting tool if there's an event
            if session_id in self.upload_events:
                self.upload_events[session_id].set()
                logger.info(f"Notified take_picture_and_analyze tool that image is ready for session {session_id}")
            
            return {
                "success": True,
                "message": "Image stored successfully",
                "session_id": session_id
            }
            
        except Exception as e:
            logger.error(f"Error storing image for session {session_id}: {e}")
            return {
                "success": False,
                "error": str(e)
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