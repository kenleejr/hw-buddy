"""
HW Buddy Live Agent using Google ADK Live API
This agent handles real-time audio streaming and image analysis for homework tutoring.
"""

import asyncio
import logging
import re
import json
from typing import Dict, Any, AsyncIterator
import firebase_admin
from firebase_admin import credentials, firestore

# Google ADK imports
from google.adk.agents import Agent, LiveRequestQueue
from google.adk.runners import Runner
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool, ToolContext
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from google.genai import types
from google.genai.types import Part, UserContent, Content

# Local imports
from prompts import HINT_AGENT_PROMPT

# Configure logging
logger = logging.getLogger(__name__)

def log_expert_flow(stage: str, session_id: str = None, expert_session_id: str = None, 
                   data: dict = None, error: str = None):
    """
    Detailed logging function for expert agent flow tracking.
    """
    prefix = f"🔍 EXPERT_FLOW"
    
    if error:
        logger.error(f"{prefix} [{stage}] ERROR: {error}")
        if data:
            logger.error(f"{prefix} [{stage}] ERROR_DATA: {data}")
    else:
        log_msg = f"{prefix} [{stage}]"
        if session_id:
            log_msg += f" session={session_id}"
        if expert_session_id:
            log_msg += f" expert_session={expert_session_id}"
        if data:
            log_msg += f" data={data}"
        
        logger.info(log_msg)

# Disable verbose logging from Google ADK modules
logging.getLogger('google_adk.google.adk.models.google_llm').setLevel(logging.WARNING)
logging.getLogger('google.adk.models.google_llm').setLevel(logging.WARNING)
logging.getLogger('google_genai.models').setLevel(logging.WARNING)
logging.getLogger('google_genai.types').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)

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

def clean_visualization_response(response_text: str) -> str:
    """
    Clean visualization agent response by removing markdown formatting.
    Same as clean_agent_response but without MathJax escaping since visualizations don't need it.
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
    
    # Try to parse and re-encode as JSON to fix any formatting issues
    try:
        # If it's valid JSON, parse and re-encode to ensure proper escaping
        parsed = json.loads(cleaned)
        # Re-encode with proper escaping
        cleaned = json.dumps(parsed, ensure_ascii=False)
        logger.info("Successfully re-encoded visualization response as proper JSON")
    except json.JSONDecodeError as e:
        logger.warning(f"Visualization response has malformed JSON, attempting to fix: {e}")
        # Try to fix common JSON issues like unescaped newlines and quotes
        try:
            fixed_json = fix_malformed_json(cleaned)
            parsed = json.loads(fixed_json)
            cleaned = json.dumps(parsed, ensure_ascii=False)
            logger.info("Successfully fixed and re-encoded malformed visualization JSON")
        except Exception as fix_error:
            logger.error(f"Could not fix malformed visualization JSON: {fix_error}")
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
#MODEL = "gemini-2.0-flash-live-001"
MODEL="gemini-2.5-flash-preview-native-audio-dialog"

# System instruction for the homework tutor
# SYSTEM_INSTRUCTION = """You are a text to speech and speech to text system. Your sole responsibility is to relay information such as user questions to a backend expert help agent.  \
#               When the agent returns, you relay its response back to the user. \
#               When a user asks you for help, you need to ALWAYS call the get_expert_help function. \
#               This calls an agent which WILL TAKE A PICTURE of their homework and give them guidance on how to help them. \
#               Pass the user's specific question or request as the 'user_ask' parameter to the get_expert_help function. \
#               This function will analyze the student's progress and return with "help_text" which you can relay back to the user."""

SYSTEM_INSTRUCTION = """You are an AI tutor assistant helping with communication between students and an EXPERT TUTOR AI system.  \
              Your task is to ALWAYS pass the user questions and requests to the EXPERT AI TUTOR and to relay back to the student all the content and communication sent from the EXPERT AI TUTOR to you.  \
              ALWAYS say ok, one moment before executing a TOOL CALL. \
              ALWAYS Pass the user's specific question or request as the `user_ask` parameter to the `get_expert_help` function. \
              This function will communicate with the expert ai tutor and return with "help_text" which you can relay back to the user."""


class HWBuddyLiveAgent:
    """Live agent for homework tutoring with real-time audio and image processing."""
    
    def __init__(self):
        self.sessions: Dict[str, Any] = {}
        # Separate session services for live and expert agents
        self.live_session_service = InMemorySessionService()
        self.expert_session_service = InMemorySessionService()
        
        # Initialize Firebase for Firestore communication
        self._init_firebase()
        
        # Create the expert help agent (simplified without sequential agent)
        self.expert_help_agent = self._create_expert_help_agent()
        
        # Create the expert help runner using separate session service
        self.expert_help_runner = Runner(
            app_name="hw_buddy_expert",  # Different app name for expert
            agent=self.expert_help_agent,
            session_service=self.expert_session_service,  # Separate session service
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
            tools=[self.get_expert_help_tool]
        )
        
        # Create runner for managing agent interactions
        self.runner = Runner(
            app_name="hw_buddy_live",
            agent=self.agent,
            session_service=self.live_session_service,
        )
        
        logger.info("HW Buddy Live Agent initialized")
    
    def _create_expert_help_agent(self) -> LlmAgent:
        """Create a single, simple expert agent that can take pictures and provide help directly."""
        
        # Create the take_picture tool
        def create_take_picture_tool():
            async def take_picture_tool(tool_context: ToolContext) -> str:
                """
                Simple tool to capture an image of the student's work.
                """
                try:
                    # Get current session ID
                    current_session_id = getattr(self, 'current_session_id', None)
                    if not current_session_id and self.sessions:
                        current_session_id = list(self.sessions.keys())[0]
                    
                    if not current_session_id:
                        logger.error("No session_id found for picture capture")
                        return "Error: Could not identify the current session."
                    
                    logger.info(f"📸 Expert agent requesting picture for session {current_session_id}")
                    
                    # Trigger picture taking via Firestore
                    if self.db:
                        session_ref = self.db.collection('sessions').document(current_session_id)
                        doc = session_ref.get()
                        if doc.exists:
                            session_ref.update({'command': 'take_picture'})
                        else:
                            session_ref.set({'command': 'take_picture', 'session_id': current_session_id})
                        logger.info(f"📸 Sent take_picture command for session {current_session_id}")
                        
                        # Wait for the image to be captured
                        await asyncio.sleep(4)  # Give time for image capture
                        
                        # The image should now be available in session state
                        # The inject_image_callback will handle injecting it into the next LLM call
                        logger.info("📸 Image capture completed, will be available for analysis")
                        return "Image captured successfully. I can now see the student's work."
                    else:
                        logger.error("📸 Database not available, cannot send take_picture command")
                        return "Error: Picture capture service not available."
                    
                except Exception as e:
                    logger.error(f"Error in take_picture_tool: {str(e)}")
                    return f"Error capturing image: {str(e)}"
            
            return take_picture_tool
        
        # Create the take picture function tool
        take_picture_function_tool = FunctionTool(
            func=create_take_picture_tool()
        )
        
        # Create a before model callback to inject context from live session and images
        def inject_live_context_and_image(callback_context: CallbackContext, llm_request: LlmRequest):
            """
            Before model callback that injects latest events from live session and images.
            """
            # Get current session ID from expert context
            current_session_id = getattr(self, 'current_session_id', None)
            
            log_expert_flow("BEFORE_MODEL_CALLBACK_START", 
                          session_id=current_session_id,
                          data={"has_llm_request": bool(llm_request), 
                                "request_contents_count": len(llm_request.contents) if llm_request.contents else 0})
            
            if current_session_id:
                log_expert_flow("CONTEXT_INJECTION_START", session_id=current_session_id)
                
                try:
                    # Get the live session synchronously from the service's internal storage
                    # InMemorySessionService stores sessions as: app_name -> user_id -> session_id -> session
                    live_session = None
                    
                    if hasattr(self.live_session_service, 'sessions'):
                        app_sessions = self.live_session_service.sessions.get("hw_buddy_live", {})
                        user_sessions = app_sessions.get(f"student_{current_session_id}", {})
                        live_session = user_sessions.get(current_session_id, None)
                    
                    if not live_session:
                        log_expert_flow("CONTEXT_INJECTION_ERROR", 
                                      session_id=current_session_id,
                                      error="Could not find live session for context injection")
                        return
                    
                    log_expert_flow("LIVE_SESSION_FOUND", 
                                  session_id=current_session_id,
                                  data={"events_count": len(live_session.events) if hasattr(live_session, 'events') and live_session.events else 0,
                                        "has_state": hasattr(live_session, 'state')})
                    
                    if live_session and hasattr(live_session, 'events') and live_session.events:
                        # Get the last few relevant events from live session
                        recent_events = live_session.events[-5:]  # Last 5 events
                        
                        # Build context from recent events
                        context_parts = []
                        for event in recent_events:
                            if hasattr(event, 'content') and event.content and hasattr(event.content, 'parts'):
                                for part in event.content.parts:
                                    if hasattr(part, 'text') and part.text:
                                        context_parts.append(f"[{event.author}]: {part.text}")
                        
                        if context_parts:
                            context_text = "Recent conversation context:\n" + "\n".join(context_parts[-3:])  # Last 3 relevant messages
                            
                            # Inject the context at the beginning of the request
                            if not llm_request.contents:
                                llm_request.contents = []
                            
                            context_content = Content(role="user", parts=[Part(text=context_text)])
                            llm_request.contents.insert(0, context_content)
                            
                            log_expert_flow("CONTEXT_INJECTED", 
                                          session_id=current_session_id,
                                          data={"context_parts_count": len(context_parts),
                                                "context_text_preview": context_text[:100] + "..." if len(context_text) > 100 else context_text})
                    
                    # Also check for images in the live session state
                    if live_session and hasattr(live_session, 'state'):
                        # 🔍 DEBUG: Log what's actually in the live session state
                        state_keys = list(live_session.state.keys()) if live_session.state else []
                        log_expert_flow("LIVE_SESSION_STATE_CHECK", 
                                      session_id=current_session_id,
                                      data={"state_keys": state_keys, 
                                            "has_state": bool(live_session.state)})
                        
                        current_image_bytes = live_session.state.get("temp:current_image_bytes")
                        current_image_mime_type = live_session.state.get("temp:current_image_mime_type", "image/jpeg")
                        
                        log_expert_flow("LIVE_SESSION_IMAGE_CHECK", 
                                      session_id=current_session_id,
                                      data={"has_image_bytes": bool(current_image_bytes),
                                            "image_bytes_length": len(current_image_bytes) if current_image_bytes else 0})
                        
                        # If no image in session state, check our local sessions dict
                        if not current_image_bytes and current_session_id in self.sessions:
                            current_image_bytes = self.sessions[current_session_id].get("current_image_bytes")
                            current_image_mime_type = self.sessions[current_session_id].get("current_image_mime_type", "image/jpeg")
                            
                            if current_image_bytes:
                                log_expert_flow("IMAGE_FOUND_IN_LOCAL_SESSIONS", 
                                              session_id=current_session_id,
                                              data={"image_bytes": len(current_image_bytes),
                                                    "mime_type": current_image_mime_type})
                        
                        if current_image_bytes:
                            log_expert_flow("IMAGE_INJECTION_FROM_LIVE", 
                                          session_id=current_session_id,
                                          data={"image_bytes": len(current_image_bytes), 
                                                "mime_type": current_image_mime_type})
                            
                            # 🔍 DEBUG: Save image locally to verify what expert receives
                            try:
                                import os
                                debug_dir = "/tmp/hw_buddy_debug"
                                os.makedirs(debug_dir, exist_ok=True)
                                
                                # Save with timestamp and session ID
                                import time
                                timestamp = int(time.time())
                                debug_filename = f"{debug_dir}/expert_image_{current_session_id}_{timestamp}.jpg"
                                
                                with open(debug_filename, 'wb') as f:
                                    f.write(current_image_bytes)
                                
                                log_expert_flow("IMAGE_SAVED_FOR_DEBUG", 
                                              session_id=current_session_id,
                                              data={"debug_file": debug_filename, 
                                                    "file_size": len(current_image_bytes)})
                                
                            except Exception as e:
                                log_expert_flow("IMAGE_DEBUG_SAVE_ERROR", 
                                              session_id=current_session_id,
                                              error=str(e))
                            
                            # Create image part from raw bytes
                            image_part = Part.from_bytes(
                                data=current_image_bytes,
                                mime_type=current_image_mime_type
                            )
                            
                            # Add the image content to the LLM request
                            if not llm_request.contents:
                                llm_request.contents = []
                            
                            # Insert the image content as a user message
                            image_content = Content(role="user", parts=[image_part])
                            llm_request.contents.append(image_content)
                            
                            log_expert_flow("IMAGE_INJECTED_SUCCESS", session_id=current_session_id)
                
                except Exception as e:
                    log_expert_flow("CONTEXT_INJECTION_ERROR", 
                                  session_id=current_session_id,
                                  error=str(e))
                    
            # Also check for images in the expert session state (fallback)
            current_image_bytes = callback_context.state.get("temp:current_image_bytes")
            current_image_mime_type = callback_context.state.get("temp:current_image_mime_type", "image/jpeg")
            
            if current_image_bytes:
                log_expert_flow("IMAGE_INJECTION_FROM_EXPERT", 
                              session_id=current_session_id,
                              data={"image_bytes": len(current_image_bytes), 
                                    "mime_type": current_image_mime_type})
                
                # 🔍 DEBUG: Save expert session image locally to verify
                try:
                    import os
                    debug_dir = "/tmp/hw_buddy_debug"
                    os.makedirs(debug_dir, exist_ok=True)
                    
                    # Save with timestamp and session ID
                    import time
                    timestamp = int(time.time())
                    debug_filename = f"{debug_dir}/expert_session_image_{current_session_id}_{timestamp}.jpg"
                    
                    with open(debug_filename, 'wb') as f:
                        f.write(current_image_bytes)
                    
                    log_expert_flow("EXPERT_SESSION_IMAGE_SAVED_FOR_DEBUG", 
                                  session_id=current_session_id,
                                  data={"debug_file": debug_filename, 
                                        "file_size": len(current_image_bytes)})
                    
                except Exception as e:
                    log_expert_flow("EXPERT_SESSION_IMAGE_DEBUG_SAVE_ERROR", 
                                  session_id=current_session_id,
                                  error=str(e))
                
                # Create image part from raw bytes
                image_part = Part.from_bytes(
                    data=current_image_bytes,
                    mime_type=current_image_mime_type
                )
                
                # Add the image content to the LLM request
                if not llm_request.contents:
                    llm_request.contents = []
                
                # Insert the image content as a user message
                image_content = Content(role="user", parts=[image_part])
                llm_request.contents.append(image_content)
                
                log_expert_flow("IMAGE_INJECTED_FROM_EXPERT_SUCCESS", session_id=current_session_id)
            
            # 🔍 DEBUG: Log detailed request structure
            request_debug_info = {"final_request_contents_count": len(llm_request.contents) if llm_request.contents else 0}
            
            if llm_request.contents:
                content_details = []
                for i, content in enumerate(llm_request.contents):
                    content_info = {
                        "index": i,
                        "role": content.role if hasattr(content, 'role') else "unknown",
                        "parts_count": len(content.parts) if hasattr(content, 'parts') and content.parts else 0
                    }
                    
                    if hasattr(content, 'parts') and content.parts:
                        part_types = []
                        for part in content.parts:
                            if hasattr(part, 'text') and part.text:
                                part_types.append(f"text({len(part.text)} chars)")
                            elif hasattr(part, 'inline_data'):
                                part_types.append(f"image({part.inline_data.mime_type if hasattr(part.inline_data, 'mime_type') else 'unknown'})")
                            else:
                                part_types.append("unknown_part")
                        content_info["part_types"] = part_types
                    
                    content_details.append(content_info)
                
                request_debug_info["content_details"] = content_details
            
            log_expert_flow("BEFORE_MODEL_CALLBACK_COMPLETE", 
                          session_id=current_session_id,
                          data=request_debug_info)
        
        # Create a single smart expert agent
        expert_agent = LlmAgent(
            name="ExpertTutorAgent", 
            model="gemini-2.5-flash",  # Using flash for speed and reliability
            tools=[take_picture_function_tool],
            before_model_callback=inject_live_context_and_image,
            instruction="""You are an expert homework tutor AI that provides personalized, step-by-step guidance to help students learn and understand their homework problems.

AVAILABLE TOOLS:
- "take_picture_tool" - Capture an image of the student's work when visual context is needed

CORE PRINCIPLES:
1. **Student-Centered Learning**: Guide students to discover answers themselves rather than giving direct solutions
2. **Visual Context**: When a student asks for help with a specific problem, use take_picture_tool to see their actual work
3. **Adaptive Teaching**: Adjust your approach based on the student's level and understanding
4. **Encourage Growth**: Build confidence through positive reinforcement and incremental progress

RESPONSE FORMAT:
Always return a JSON response with this structure:
{
  "help_text": "Your helpful, educational response to the student",
  "reasoning": "Brief explanation of your tutoring approach for this response"
}

TUTORING APPROACH:
- **For specific homework problems**: Use take_picture_tool first to see their work, then provide targeted guidance
- **For conceptual questions**: Explain concepts using simple analogies and examples
- **For stuck students**: Break problems into smaller, manageable steps
- **For incorrect work**: Gently guide them to identify and correct mistakes
- **For correct work**: Acknowledge their success and suggest next steps or extensions

EXAMPLES:
- If student says "I need help with this math problem" → Use take_picture_tool, then guide them through the specific problem you see
- If student asks "How do I solve quadratic equations?" → Explain the concept and methods step-by-step
- If student shows completed work → Review it and provide constructive feedback

Remember: You're here to help students LEARN, not just get answers. Always encourage their thinking process and celebrate their efforts."""
        )
        
        return expert_agent
    
    def _create_get_expert_help_function(self):
        """Create a simple get_expert_help function using direct agent interaction."""
        async def get_expert_help(tool_context: ToolContext, user_ask: str) -> str:
            """
            Get expert help using direct agent interaction - much simpler and faster.
            """
            try:
                import time
                
                # Rate limiting check
                current_time = time.time()
                last_call_time = tool_context.state.get("last_expert_help_time", 0)
                time_since_last_call = current_time - last_call_time
                
                if time_since_last_call < 3.0 and last_call_time > 0:
                    logger.info(f"⚠️ Rate limiting: Expert help called {time_since_last_call:.1f}s ago")
                    return "Still processing your previous request. Please wait a moment..."
                
                # Update the last call time
                tool_context.state["last_expert_help_time"] = current_time
                
                # Get current session ID
                current_session_id = getattr(self, 'current_session_id', None)
                if not current_session_id and self.sessions:
                    current_session_id = list(self.sessions.keys())[0]
                
                if not current_session_id:
                    logger.error("No session_id found for expert help")
                    return "I apologize, but I couldn't access the session to help you."
                
                log_expert_flow("GET_EXPERT_HELP_START", 
                               session_id=current_session_id,
                               data={"user_ask": user_ask, "time_since_last_call": time_since_last_call})
                
                # Create separate expert session with unique ID
                expert_session_id = f"expert_{current_session_id}"
                live_user_id = self.sessions[current_session_id]["adk_session"].user_id
                
                log_expert_flow("EXPERT_SESSION_SETUP", 
                               session_id=current_session_id,
                               expert_session_id=expert_session_id,
                               data={"live_user_id": live_user_id})
                
                # Create or get expert session
                try:
                    expert_session = await self.expert_session_service.get_session(
                        app_name="hw_buddy_expert",
                        user_id=live_user_id,
                        session_id=expert_session_id
                    )
                    if not expert_session:
                        expert_session = await self.expert_session_service.create_session(
                            app_name="hw_buddy_expert",
                            user_id=live_user_id,
                            session_id=expert_session_id
                        )
                        log_expert_flow("EXPERT_SESSION_CREATED", 
                                       session_id=current_session_id,
                                       expert_session_id=expert_session_id)
                    else:
                        log_expert_flow("EXPERT_SESSION_REUSED", 
                                       session_id=current_session_id,
                                       expert_session_id=expert_session_id)
                except Exception as e:
                    log_expert_flow("EXPERT_SESSION_ERROR", 
                                   session_id=current_session_id,
                                   error=str(e))
                    return "I apologize, but I couldn't create an expert session to help you."
                
                # Use separate expert session
                run_config = RunConfig(
                    streaming_mode=StreamingMode.NONE,
                    max_llm_calls=3  # Keep it simple and fast
                )
                
                # Create user content with the question
                content = UserContent(parts=[Part(text=user_ask)])
                
                log_expert_flow("EXPERT_AGENT_RUN_START", 
                               session_id=current_session_id,
                               expert_session_id=expert_session_id,
                               data={"max_llm_calls": run_config.max_llm_calls})
                
                # Run the expert agent using separate session
                final_response = ""
                event_count = 0
                async for event in self.expert_help_runner.run_async(
                    session_id=expert_session_id,  # Separate expert session
                    new_message=content,
                    run_config=run_config,
                    user_id=live_user_id
                ):
                    event_count += 1
                    log_expert_flow("EXPERT_EVENT_RECEIVED", 
                                   session_id=current_session_id,
                                   expert_session_id=expert_session_id,
                                   data={"event_count": event_count, 
                                         "event_author": event.author,
                                         "is_final": event.is_final_response()})
                    # Check for final response
                    if event.is_final_response() and event.author == "ExpertTutorAgent":
                        log_expert_flow("EXPERT_FINAL_RESPONSE_FOUND", 
                                       session_id=current_session_id,
                                       expert_session_id=expert_session_id,
                                       data={"has_content": bool(event.content)})
                        
                        if event.content:
                            for part in event.content.parts:
                                if hasattr(part, 'text') and part.text:
                                    raw_response = part.text
                                    
                                    log_expert_flow("EXPERT_RESPONSE_PROCESSING", 
                                                   session_id=current_session_id,
                                                   expert_session_id=expert_session_id,
                                                   data={"raw_response_length": len(raw_response),
                                                         "raw_response_preview": raw_response[:200] + "..." if len(raw_response) > 200 else raw_response})
                                    
                                    # Clean the response
                                    cleaned_response = clean_agent_response(raw_response)
                                    
                                    # Try to parse as JSON and extract help_text
                                    try:
                                        parsed_response = json.loads(cleaned_response)
                                        if isinstance(parsed_response, dict) and "help_text" in parsed_response:
                                            final_response = parsed_response["help_text"]
                                            log_expert_flow("EXPERT_RESPONSE_EXTRACTED", 
                                                           session_id=current_session_id,
                                                           expert_session_id=expert_session_id,
                                                           data={"help_text_length": len(final_response)})
                                        else:
                                            final_response = cleaned_response
                                            log_expert_flow("EXPERT_RESPONSE_DIRECT", 
                                                           session_id=current_session_id,
                                                           expert_session_id=expert_session_id)
                                    except json.JSONDecodeError:
                                        # If not JSON, use the response directly
                                        final_response = cleaned_response
                                        log_expert_flow("EXPERT_RESPONSE_NOT_JSON", 
                                                       session_id=current_session_id,
                                                       expert_session_id=expert_session_id)
                                    
                                    break
                
                log_expert_flow("GET_EXPERT_HELP_COMPLETE", 
                               session_id=current_session_id,
                               expert_session_id=expert_session_id,
                               data={"final_response_length": len(final_response) if final_response else 0,
                                     "has_response": bool(final_response)})
                
                return final_response or "I've analyzed your request and provided guidance above."
                
            except Exception as e:
                log_expert_flow("GET_EXPERT_HELP_ERROR", 
                               session_id=current_session_id,
                               error=str(e))
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
            adk_session = await self.live_session_service.create_session(
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
        
        # Store session data (no separate expert session needed)
        session_data = {
            "session_id": session_id,
            "adk_session": adk_session,
            "live_request_queue": live_request_queue,
            "run_config": run_config,
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
        Store an uploaded image directly in the shared session state.
        This is called by the image upload handler when an image is received.
        
        Args:
            session_id: The session ID
            image_data: Raw image bytes
            mime_type: MIME type of the image
            
        Returns:
            Storage confirmation
        """
        try:
            # Get the session to access its state
            session = await self.live_session_service.get_session(
                app_name="hw_buddy_live",
                user_id=self.sessions[session_id]["adk_session"].user_id,
                session_id=session_id
            )
            
            if not session:
                raise ValueError(f"Session {session_id} not found")
            
            # Store image data directly in session state
            # We need to create an event to update the state
            from google.adk.events import Event, EventActions
            import time
            
            state_updates = {
                "temp:current_image_bytes": image_data,
                "temp:current_image_mime_type": mime_type,
                "temp:image_upload_time": time.time()
            }
            
            # Create an event with state updates
            update_event = Event(
                invocation_id=f"image_upload_{session_id}",
                author="system",
                actions=EventActions(state_delta=state_updates),
                timestamp=time.time()
            )
            
            # Append the event to update state
            await self.live_session_service.append_event(session, update_event)
            
            # ALSO store in our local sessions dict for quick access during context injection
            if session_id in self.sessions:
                self.sessions[session_id]["current_image_bytes"] = image_data
                self.sessions[session_id]["current_image_mime_type"] = mime_type
                self.sessions[session_id]["image_upload_time"] = time.time()
            
            logger.info(f"📸 Stored image in session state for {session_id}: {len(image_data)} bytes, type: {mime_type}")
            
            return {
                "success": True,
                "message": "Image stored successfully in session state",
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
        }


# Global instance
hw_live_agent = HWBuddyLiveAgent()


def get_hw_live_agent() -> HWBuddyLiveAgent:
    """Get the global homework live agent instance."""
    return hw_live_agent