"""
HW Buddy Tutor Agent using Google ADK
This agent intelligently decides when to take pictures based on the conversation context.
"""

import asyncio
import json
import logging
import traceback
import re
from typing import Dict, Any, Optional
from google import genai
from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.runners import Runner
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.sessions import InMemorySessionService
from google.adk.artifacts import InMemoryArtifactService
from google.adk.tools import FunctionTool, ToolContext
from google.adk.tools.agent_tool import AgentTool
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from google.genai.types import Part, UserContent, Content
from google.adk.events import Event, EventActions
from firebase_admin import firestore
from prompts import *

# Configure logging for this module
logger = logging.getLogger(__name__)


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


class HWTutorAgent:
    """
    A homework tutor agent that intelligently uses tools like taking pictures
    based on the conversation context and student needs.
    """
    
    def __init__(self, db: firestore.Client, connection_manager=None):
        logger.info("Initializing HWTutorAgent...")
        self.db = db
        self.connection_manager = connection_manager
        
        logger.info("Creating session and artifact services...")
        self.session_service = InMemorySessionService()
        self.artifact_service = InMemoryArtifactService()
        logger.info("Services created successfully")
        
        # Create the take_picture tool using a closure
        logger.info("Creating take_picture tool...")
        
        def create_take_picture_and_analyze_function(db):
            async def take_picture_and_analyze_tool(tool_context: ToolContext, user_ask: str) -> str:
                """
                Tool that triggers image capture and retrieves raw image bytes.
                The image bytes are stored in context for injection into the next LLM request.
                """
                try:
                    session_id = tool_context._invocation_context.session.id
                    if not session_id:
                        logger.error(f"Tool context state: {tool_context.state}")
                        logger.error("No session_id found in tool context state")
                        raise Exception("No session_id found in context")
                    
                    logger.info(f"Taking picture for session {session_id}, user_ask: {user_ask}")
                    
                    # Ensure session exists in Firestore for mobile app coordination
                    session_ref = db.collection('sessions').document(session_id)
                    current_doc = session_ref.get()
                    
                    if not current_doc.exists:
                        raise Exception(f"Session {session_id} not found")
                    
                    # Create event and register it for direct notification
                    upload_event = asyncio.Event()
                    from main import upload_events, session_images
                    upload_events[session_id] = upload_event
                    
                    # Trigger picture taking
                    session_ref.update({'command': 'take_picture'})
                    logger.info(f"Sent take_picture command to session {session_id}")
                    
                    # Wait for direct notification from upload endpoint
                    try:
                        await asyncio.wait_for(upload_event.wait(), timeout=30)
                        logger.info(f"Received upload notification for session {session_id}")
                    except asyncio.TimeoutError:
                        raise Exception(f"Timeout waiting for image upload from session {session_id}")
                    finally:
                        # Clean up event to prevent memory leaks
                        if session_id in upload_events:
                            del upload_events[session_id]
                    
                    # Get raw image bytes from session storage
                    if session_id not in session_images:
                        raise Exception(f"No image data found for session {session_id}")
                    
                    image_data = session_images[session_id]
                    image_bytes = image_data['bytes']
                    mime_type = image_data['mime_type']
                    
                    logger.info(f"Retrieved image data: {len(image_bytes)} bytes, type: {mime_type}")
                    
                    # Store image bytes in context for injection callback
                    tool_context.state["pending_image_bytes"] = image_bytes
                    tool_context.state["pending_image_mime_type"] = mime_type
                    tool_context.state["pending_user_ask"] = user_ask
                    
                    return "Image captured successfully. I can now see your homework."
                    
                except Exception as e:
                    logger.error(f"Error in take_picture_and_analyze_tool: {str(e)}")
                    logger.error(f"Full traceback: {traceback.format_exc()}")
                    return f"Error capturing image: {str(e)}"
            
            return take_picture_and_analyze_tool
        
        self.take_picture_tool = FunctionTool(
            func=create_take_picture_and_analyze_function(self.db)
        )
        logger.info("Take_picture tool created successfully")

        async def before_agent_callback1(callback_context: CallbackContext) -> Optional[Content]:
            user_interaction_count = callback_context.state.get("user_interaction_count", 0)
            if user_interaction_count == 0:
                callback_context.state["problem_at_hand"] = "None"
            elif callback_context.state.get("problem_at_hand", None):
                callback_context.state["problem_at_hand"] = "None"

            callback_context.state["user_interaction_count"] = user_interaction_count + 1
            return None
    
        
        # Define the before_model_callback to inject images
        def inject_image_callback(callback_context: CallbackContext, llm_request: LlmRequest):
            """
            Before model callback that injects pending image bytes into the LLM request.
            Uses raw image bytes instead of URI for better performance and simplicity.
            """
            # Check if there are pending image bytes to inject
            pending_image_bytes = callback_context.state.get("pending_image_bytes")
            pending_mime_type = callback_context.state.get("pending_image_mime_type", "image/jpeg")
            
            if pending_image_bytes:
                logger.info(f"Injecting image bytes into LLM request: {len(pending_image_bytes)} bytes, type: {pending_mime_type}")
                
                # Create image part from raw bytes - much cleaner than URI!
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

        self.hint_agent = LlmAgent(
            name="HintAgent",
            model="gemini-2.5-flash",
            instruction=HINT_AGENT_PROMPT
        )
        
        # Create the main tutoring agent
        self.state_establisher_agent = LlmAgent(
            name="StateEstablisher",
            model="gemini-2.5-flash",
            tools=[self.take_picture_tool],
            before_model_callback=inject_image_callback,
            output_key="problem_at_hand",
            instruction=STATE_ESTABLISHER_AGENT_PROMPT
        )

        self.root_agent = SequentialAgent(
            name="root_agent",
            before_agent_callback=[before_agent_callback1],
            sub_agents=[self.state_establisher_agent, self.hint_agent]
        )
        
        # Create the runner
        self.runner = Runner(
            agent=self.root_agent,
            app_name="hw-buddy-tutor",
            session_service=self.session_service,
            artifact_service=self.artifact_service
        )
    
    async def _send_event_update(self, session_id: str, event):
        """Send relevant ADK event updates via WebSocket"""
        try:
            # Log the raw event for debugging
            logger.info(f"🔍 RAW ADK EVENT - Content: {getattr(event, 'content', None)}")
            logger.info(f"🔍 RAW ADK EVENT - Author: {getattr(event, 'author', None)}")
            logger.info(f"🔍 RAW ADK EVENT - Actions: {getattr(event, 'actions', None)}")
            
            # Analyze the event and send meaningful updates
            event_data = {
                "event_id": getattr(event, 'id', ''),
                "author": getattr(event, 'author', ''),
                "timestamp": getattr(event, 'timestamp', 0),
                "is_final": event.is_final_response() if hasattr(event, 'is_final_response') else False
            }
            
            # Check for function calls (like taking pictures)
            function_calls = event.get_function_calls() if hasattr(event, 'get_function_calls') else []
            if function_calls:
                for func_call in function_calls:
                    if func_call.name == 'take_picture_and_analyze_tool':
                        event_data["function_call"] = {
                            "name": func_call.name,
                            "args": func_call.args if hasattr(func_call, 'args') else {}
                        }
            
            # Check for function responses
            function_responses = event.get_function_responses() if hasattr(event, 'get_function_responses') else []
            if function_responses:
                for func_response in function_responses:
                    if func_response.name == 'take_picture_and_analyze_tool':
                        event_data["function_response"] = {
                            "name": func_response.name,
                            "response": str(func_response.response) if hasattr(func_response, 'response') else ""
                        }
            
            # Check for text content (agent thinking/responding)
            if hasattr(event, 'content') and event.content and hasattr(event.content, 'parts'):
                for part in event.content.parts:
                    if hasattr(part, 'text') and part.text:
                        event_data["has_text_content"] = True
                        # Include the actual content for parsing
                        if not event_data.get("content"):
                            event_data["content"] = {"parts": []}
                        event_data["content"]["parts"].append({"text": part.text})
                        break
            
            # Send the processed event data
            logger.info(f"🔍 Sending adk_event with data: {event_data}")
            await self.connection_manager.send_event_update(session_id, "adk_event", event_data)
            
        except Exception as e:
            logger.error(f"Error sending event update: {e}")
            # Don't let event processing errors break the main flow
        
    async def process_user_query(self, session_id: str, user_query: str) -> dict:
        """
        Process a user query using the ADK agent with session management.
        Returns a dictionary with response text and image URLs if a picture was taken.
        """
        try:
            # Create session first (InMemorySessionService requires creating before getting)
            try:
                session = await self.session_service.create_session(
                    session_id=session_id,
                    app_name="hw-buddy-tutor",
                    user_id="student"
                )
                logger.info(f"Created new session: {session.id}")
            except Exception as create_error:
                logger.info(f"Session creation failed (might already exist): {create_error}")
                # Try to get existing session
                session = await self.session_service.get_session(
                    session_id=session_id,
                    user_id="student",
                    app_name="hw-buddy-tutor"
                )
            
            if session is None:
                logger.error("Failed to create or get session")
                return "I encountered an error creating a session. Please try again."
            
            # Store session_id in session state for tools to use
            # We'll pass this via the user input content since direct session state modification
            # isn't the recommended approach
            logger.info(f"Will pass session_id {session_id} to agent context")
            
            # Create run config
            run_config = RunConfig(
                streaming_mode=StreamingMode.NONE,
                max_llm_calls=10
            )
            
            # Run the agent using the actual session ID from the created/retrieved session
            response_events = []
            content = UserContent(parts=[Part(text=user_query)])
            logger.info(f"Starting agent run with session_id: {session.id}, user_id: student")
            
            final_response_data = None
            
            async for event in self.runner.run_async(
                session_id=session.id,  # Use the actual session ID
                new_message=content,
                user_id="student",
                run_config=run_config
            ):
                
                response_events.append(event)
                
                # Send real-time event updates via WebSocket
                if self.connection_manager:
                    await self._send_event_update(session_id, event)
                
                # Check if this is a final response but don't return yet - collect it
                if event.is_final_response() and not final_response_data and event.author == "root_agent":
                    logger.info("Found final response event!")
                    # Extract text content
                    if event.content:
                        for part in event.content.parts:
                            logger.info(f"Checking part: {part}")
                            if hasattr(part, 'text') and part.text:
                                logger.info(f"Found text in part: {part.text}")
                                # Clean the response text to remove markdown formatting
                                response_text = clean_agent_response(part.text)
                                logger.info(f"Cleaned response text: {response_text}")
                                
                                # Store just the response text for now
                                # We'll get the image URLs after the loop when state is persisted
                                final_response_data = {
                                    "response": response_text,
                                    "image_url": None,
                                    "image_gcs_url": None
                                }
                
            # After the loop, get image URLs from the updated session state
            if final_response_data:
                # Fetch the updated session to get the latest state after tool execution
                try:
                    updated_session = await self.session_service.get_session(
                        session_id=session.id,
                        user_id="student",
                        app_name="hw-buddy-tutor"
                    )
                    
                    if updated_session and updated_session.state:
                        image_url = updated_session.state.get("last_image_url")
                        image_gcs_url = updated_session.state.get("last_image_gcs_url")
                        logger.info(f"Retrieved image URLs from updated session - image_url: {image_url}, image_gcs_url: {image_gcs_url}")
                    else:
                        logger.warning("Could not retrieve updated session or session has no state")
                        image_url = None
                        image_gcs_url = None
                        
                except Exception as e:
                    logger.error(f"Error retrieving updated session: {e}")
                    # Fallback to original session state
                    image_url = session.state.get("last_image_url") if session.state else None
                    image_gcs_url = session.state.get("last_image_gcs_url") if session.state else None
                
                # Update the response data with the image URLs
                final_response_data["image_url"] = image_url
                final_response_data["image_gcs_url"] = image_gcs_url
                
                logger.info(f"Final response with image URLs - text: {final_response_data['response'][:100]}..., image_url: {image_url}, image_gcs_url: {image_gcs_url}")
                
                return final_response_data
            
            # Fallback if no final response found
            logger.info(f"No final response found. Total events received: {len(response_events)}")
            if response_events:
                last_event = response_events[-1]
                logger.info(f"Checking last event: {last_event}")
                logger.info(f"Last event content: {getattr(last_event, 'content', 'No content')}")
                
                if hasattr(last_event, 'content') and last_event.content and hasattr(last_event.content, 'parts'):
                    for part in last_event.content.parts:
                        logger.info(f"Checking last event part: {part}")
                        if hasattr(part, 'text') and part.text:
                            logger.info(f"Found text in last event part: {part.text}")
                            # Clean the response text to remove markdown formatting
                            response_text = clean_agent_response(part.text)
                            logger.info(f"Cleaned fallback response text: {response_text}")
                            
                            # Get image URLs from updated session state
                            try:
                                updated_session = await self.session_service.get_session(
                                    session_id=session.id,
                                    user_id="student",
                                    app_name="hw-buddy-tutor"
                                )
                                
                                if updated_session and updated_session.state:
                                    image_url = updated_session.state.get("last_image_url")
                                    image_gcs_url = updated_session.state.get("last_image_gcs_url")
                                else:
                                    image_url = None
                                    image_gcs_url = None
                                    
                            except Exception as e:
                                logger.error(f"Error retrieving updated session in fallback: {e}")
                                # Fallback to original session state
                                image_url = session.state.get("last_image_url") if session.state else None
                                image_gcs_url = session.state.get("last_image_gcs_url") if session.state else None
                            
                            logger.info(f"Returning fallback response - text: {response_text}, image_url: {image_url}, image_gcs_url: {image_gcs_url}")
                            
                            return {
                                "response": response_text,
                                "image_url": image_url,
                                "image_gcs_url": image_gcs_url
                            }
            
            logger.info("No usable response found, returning default message")
            return {
                "response": "I'm here to help with your homework! What would you like to work on?",
                "image_url": None,
                "image_gcs_url": None
            }
            
        except Exception as e:
            logger.error(f"Error processing user query: {str(e)}")
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return {
                "response": f"I encountered an error: {str(e)}. Let me try to help you anyway!",
                "image_url": None,
                "image_gcs_url": None
            }


# Global instance to be used by the API
hw_tutor_agent_instance: Optional[HWTutorAgent] = None

def get_hw_tutor_agent(db: firestore.Client, connection_manager=None) -> HWTutorAgent:
    """Get or create the global HW tutor agent instance."""
    global hw_tutor_agent_instance
    if hw_tutor_agent_instance is None:
        hw_tutor_agent_instance = HWTutorAgent(db, connection_manager)
    else:
        # Update connection manager for existing instance
        hw_tutor_agent_instance.connection_manager = connection_manager
    return hw_tutor_agent_instance