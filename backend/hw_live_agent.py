"""
HW Buddy Live Agent using Google ADK Live API
This agent handles real-time audio streaming and image analysis for homework tutoring.
"""

import asyncio
import logging
import traceback
import re
import json
from typing import Dict, Any, Optional, AsyncIterator, AsyncGenerator
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
MODEL = "gemini-2.0-flash-live-001"

# System instruction for the homework tutor
SYSTEM_INSTRUCTION = """You are a text to speech and speech to text system. Your sole responsibility is to relay information such as user questions to a backend expert help agent.  \
              When the agent returns, you relay its response back to the user. \
              When a user asks you for help you need to call the get_expert_help function. \
              This calls an agent which will take a picture of their homework and give you guidance on how to help them. \
              Pass the user's specific question or request as the 'user_ask' parameter to the get_expert_help function. \
              This function will analyze the student's progress and return with "help_text" which you can relay back to the user.\
                
              Example:\
                user: "I need help with number one"\
                you: "Ok I can help with that <calls expert_function with user_ask="help with number one>"\
                you: waits...
                expert_help (continuously sends updates): "<some update text>."\
                you: "<some update text>"\
                expert_help: "Here is the next step for number 1..."\
                you: "Here is the next step for number 1..."""""


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
        
        # Create the stop_streaming function tool
        def stop_streaming(function_name: str):
            """Stop the streaming tool.
            
            Args:
                function_name: The name of the streaming function to stop.
            """
            logger.info(f"Stopping streaming function: {function_name}")
            # The ADK framework handles the actual stopping
            pass
        
        self.stop_streaming_tool = FunctionTool(func=stop_streaming)
        
        # Create the ADK agent with homework tutoring capabilities
        self.agent = Agent(
            name="homework_tutor",
            model=MODEL,
            instruction=SYSTEM_INSTRUCTION,
            tools=[self.get_expert_help_tool, self.stop_streaming_tool]
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
                    
                    logger.info(f"📸 Taking picture for session {current_session_id}, user_ask: {user_ask}")
                    
                    # Check if there's already an upload event for this session
                    if current_session_id in agent_instance.upload_events:
                        logger.warning(f"📸 Upload event already exists for session {current_session_id}, cleaning up...")
                        del agent_instance.upload_events[current_session_id]
                    
                    # Create event and register it for direct notification
                    upload_event = asyncio.Event()
                    agent_instance.upload_events[current_session_id] = upload_event
                    logger.info(f"📸 Created upload event for session {current_session_id}")
                    
                    # Trigger picture taking via Firestore
                    if agent_instance.db:
                        session_ref = agent_instance.db.collection('sessions').document(current_session_id)
                        
                        # First check if the document exists
                        doc = session_ref.get()
                        if doc.exists:
                            logger.info(f"📸 Firestore document exists for session {current_session_id}")
                            # Update the existing document
                            session_ref.update({'command': 'take_picture'})
                            logger.info(f"📸 Updated take_picture command to session {current_session_id}")
                        else:
                            logger.warning(f"📸 Firestore document does not exist for session {current_session_id}, creating it")
                            # Create the document if it doesn't exist
                            session_ref.set({'command': 'take_picture', 'session_id': current_session_id})
                            logger.info(f"📸 Created new document with take_picture command for session {current_session_id}")
                        
                        # Verify the command was written
                        verification_doc = session_ref.get()
                        if verification_doc.exists:
                            data = verification_doc.to_dict()
                            logger.info(f"📸 Firestore verification - command: {data.get('command')}")
                        else:
                            logger.error(f"📸 Firestore verification failed - document still doesn't exist")
                    else:
                        logger.error("📸 Database not available, cannot send take_picture command")
                    
                    # Wait for direct notification from upload endpoint
                    try:
                        await asyncio.wait_for(upload_event.wait(), timeout=30)
                        logger.info(f"📸 Received upload notification for session {current_session_id}")
                    except asyncio.TimeoutError:
                        logger.error(f"📸 TIMEOUT waiting for image upload from session {current_session_id}")
                        logger.error(f"📸 Upload events at timeout: {list(agent_instance.upload_events.keys())}")
                        logger.error(f"📸 Session images at timeout: {list(agent_instance.session_images.keys())}")
                        raise Exception(f"Timeout waiting for image upload from session {current_session_id}")
                    finally:
                        # Clean up event to prevent memory leaks
                        if current_session_id in agent_instance.upload_events:
                            del agent_instance.upload_events[current_session_id]
                            logger.info(f"📸 Cleaned up upload event for session {current_session_id}")
                    
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
                    if current_session_id in agent_instance.session_images:
                        del agent_instance.session_images[current_session_id]
                        logger.info(f"📸 Cleaned up session image for {current_session_id}")
                    
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
        
        # Create before tool callback for rate limiting take_picture calls
        def before_tool_callback_rate_limiter(tool, args, tool_context):
            """Rate limit take_picture_and_analyze_tool calls to prevent rapid-fire requests."""
            import time
            
            # Only apply rate limiting to the take_picture tool
            if tool.name != 'take_picture_and_analyze_tool':
                return None
            
            current_time = time.time()
            last_tool_call_time = tool_context.state.get("last_take_picture_call_time", 0)
            time_since_last_call = current_time - last_tool_call_time
            
            # Rate limiting: Only allow one take_picture call every 10 seconds
            if time_since_last_call < 5.0 and last_tool_call_time > 0:
                logger.info(f"⚠️ Tool rate limiting: take_picture called {time_since_last_call:.1f}s ago, rejecting duplicate request")
                # Return a dictionary to skip the tool execution and provide a canned response
                return {"result": "Please wait a moment - still processing your previous image request..."}
            
            # Update the last call time and allow the tool to proceed
            tool_context.state["last_take_picture_call_time"] = current_time
            logger.info(f"✅ Take picture tool call allowed, updating last call time to {current_time}")
            
            return None  # Allow the tool to proceed normally
        
        # Create the hint agent (will be used as a tool)
        hint_agent = LlmAgent(
            name="HintAgent",
            model="gemini-2.5-flash",
            instruction=HINT_AGENT_PROMPT
        )
        
        # Create the visualizer agent (will be used as a tool)
        visualizer_agent = LlmAgent(
            name="VisualizerAgent",
            model="gemini-2.5-flash",
            instruction="""You are a visualization expert for math problems. Your job is to create interactive Chart.js visualizations to help students understand mathematical concepts.

Given a problem description, generate JavaScript code that creates a Chart.js visualization. Focus on:
- Systems of equations: Plot lines on a coordinate plane
- Quadratic functions: Show parabolas with key features
- Linear functions: Show lines with slope and intercepts
- Data analysis: Create appropriate charts for datasets

Return ONLY a JSON object with this structure:
{
  "visualization_type": "linear_system|quadratic|linear|data_chart",
  "chart_config": {
    // Complete Chart.js configuration object
  },
  "explanation": "Brief explanation of what the visualization shows and how it helps"
}

The chart_config should be a complete Chart.js configuration that can be passed directly to new Chart().
Use meaningful colors, labels, and formatting. Include gridlines and axis labels."""
        )
        
        # Create the help triage agent that decides between hint and visualization
        help_triage_agent = LlmAgent(
            name="HelpTriageAgent", 
            model="gemini-2.5-flash",
            sub_agents=[hint_agent, visualizer_agent],
            instruction="""You are a tutoring coordinator that decides the best way to help a student based on their question and the problem they're working on.

You have access to two tools:
1. "HintAgent" - Provides step-by-step hints and guidance
2. "VisualizerAgent" - Creates interactive visualizations (charts, graphs)

Given the user's question: {pending_user_ask} and the problem description: {problem_at_hand}, decide which approach would be most helpful:

Use HintAgent when:
- Student needs single next step hint
- Problem involves algebraic manipulation
- Student is stuck on a specific step
- Conceptual explanation is needed

Use VisualizerAgent when:
- Problem involves systems of equations (2+ variables)
- Graphing or plotting would help understanding
- Student would benefit from seeing the visual representation
- Problem involves functions, lines, parabolas, or data

Always call exactly ONE tool based on your analysis. Pass the full context including both the user's question and the problem description to the chosen tool."""
        )
        
        # Create the state establisher agent
        state_establisher_agent = LlmAgent(
            name="StateEstablisher",
            model="gemini-2.5-flash",
            tools=[take_picture_tool],
            before_model_callback=inject_image_callback,
            before_tool_callback=before_tool_callback_rate_limiter,
            output_key="problem_at_hand",
            instruction=STATE_ESTABLISHER_AGENT_PROMPT
        )
        
        # Create before agent callback with rate limiting
        async def before_agent_callback1(callback_context: CallbackContext) -> Optional[Content]:
            import time
            
            current_time = time.time()
            last_call_time = callback_context.state.get("last_expert_call_time", 0)
            time_since_last_call = current_time - last_call_time
            
            # Rate limiting: Only allow one call every 15 seconds
            if time_since_last_call < 5.0 and last_call_time > 0:
                logger.info(f"⚠️ Rate limiting: Expert help called {time_since_last_call:.1f}s ago, rejecting duplicate request")
                # Return content to skip the agent and respond with rate limit message
                return Content(
                    parts=[Part(text="Still processing your previous request. Please wait a moment...")],
                    role="model"
                )
            
            # Update the last call time
            callback_context.state["last_expert_call_time"] = current_time
            logger.info(f"✅ Expert help request allowed, updating last call time to {current_time}")
            
            # Original logic for user interaction tracking
            user_interaction_count = callback_context.state.get("user_interaction_count", 0)
            if user_interaction_count == 0:
                callback_context.state["problem_at_hand"] = "None"
            elif callback_context.state.get("problem_at_hand", None):
                callback_context.state["problem_at_hand"] = "None"
            callback_context.state["user_interaction_count"] = user_interaction_count + 1
            
            return None
        
        # Create the sequential agent with new architecture
        expert_agent = SequentialAgent(
            name="expert_help_agent",
            before_agent_callback=[before_agent_callback1],
            sub_agents=[state_establisher_agent, help_triage_agent]
        )
        
        return expert_agent
    
    def _create_get_expert_help_function(self):
        """Create the get_expert_help function that uses the independent runner."""
        async def get_expert_help(tool_context: ToolContext, user_ask: str) -> AsyncGenerator[str, None]:
            """
            Get expert help by running the independent expert help agent.
            This function streams intermediate events as they happen, allowing the live agent
            to provide real-time narration of the expert help process.
            """
            try:
                # Get current session ID for event forwarding
                current_session_id = getattr(self, 'current_session_id', None)
                if not current_session_id and self.sessions:
                    current_session_id = list(self.sessions.keys())[0]
                
                if not current_session_id:
                    logger.error("No session_id found for expert help")
                    yield "I apologize, but I couldn't access the session to help you."
                    return
                
                # Get the session data including expert session
                session_data = self.sessions.get(current_session_id)
                if not session_data:
                    logger.error(f"Session data not found for {current_session_id}")
                    yield "I apologize, but I couldn't access the session data."
                    return
                
                expert_session = session_data.get("expert_session")
                if not expert_session:
                    logger.error(f"Expert session not found for {current_session_id}")
                    yield "I apologize, but I couldn't access the expert session."
                    return
                
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
                final_response_data = None
                # Create run config
                run_config = RunConfig(
                    streaming_mode=StreamingMode.NONE,
                    max_llm_calls=10
                )
                
                # Run the agent using the actual session ID from the created/retrieved session
                content = UserContent(parts=[Part(text=user_ask)])
                async for event in self.expert_help_runner.run_async(
                    session_id=expert_session.id,
                    new_message=content,
                    run_config=run_config,
                    user_id="student"
                ):
                    # Forward events to the main session for frontend updates
                    await forward_events(current_session_id, event)
                    logger.info(f"Event from agent {event.author}")
                    logger.info(f"Event {event}")
                    
                    # Provide real-time narration based on events
                    if event.author == "HelpTriageAgent":
                        # Check for transfer_to_agent to determine what type of help is being offered
                        if hasattr(event, 'actions') and event.actions and hasattr(event.actions, 'transfer_to_agent'):
                            transfer_agent = event.actions.transfer_to_agent
                            if transfer_agent == 'HintAgent':
                                yield "I'm preparing a hint to guide you through this problem..."
                            elif transfer_agent == 'VisualizerAgent':
                                yield "I'm preparing a visualization to help you understand this better..."
    
                    
                    # Check if this is a final response but don't return yet - collect it
                    # Look for final responses from any of the expert agents
                    if event.is_final_response() and not final_response_data and event.author in ["VisualizerAgent", "HintAgent"]:
                        logger.info(f"Found final response event from {event.author}!")
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
                                    break
                
                # Yield final response if we found one
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
                    
                    yield final_response
                else:
                    yield "I've analyzed your homework and provided guidance above."
                
                logger.info(f"Expert help completed for session {current_session_id}")
                
            except Exception as e:
                logger.error(f"Error in get_expert_help: {str(e)}")
                yield f"I apologize, but I encountered an error while analyzing your homework: {str(e)}"
        
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
            
            logger.info(f"📸 Stored image for session {session_id}: {len(image_data)} bytes, type: {mime_type}")
            
            # Notify waiting tool if there's an event
            if session_id in self.upload_events:
                self.upload_events[session_id].set()
                logger.info(f"📸 Notified take_picture_and_analyze tool that image is ready for session {session_id}")
            else:
                logger.warning(f"📸 No upload event found for session {session_id} - tool may not be waiting")
            
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


# Global instance (lazy initialization)
hw_live_agent = None


def get_hw_live_agent() -> HWBuddyLiveAgent:
    """Get the global homework live agent instance."""
    global hw_live_agent
    if hw_live_agent is None:
        hw_live_agent = HWBuddyLiveAgent()
    return hw_live_agent