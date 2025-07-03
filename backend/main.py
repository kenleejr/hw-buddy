from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import firebase_admin
from firebase_admin import credentials, firestore
import os
import logging
import traceback
import json
import asyncio
from typing import Optional, Dict
from hw_tutor_agent import get_hw_tutor_agent

import base64
import os
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk import trace as trace_sdk
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry import trace

# Load sensitive values from environment variables
WANDB_BASE_URL = "https://trace.wandb.ai"
# Your W&B entity/project name e.g. "myteam/myproject"
PROJECT_ID = os.environ.get("WANDB_PROJECT_ID")  
# Your W&B API key (found at https://wandb.ai/authorize)
WANDB_API_KEY = os.environ.get("WANDB_API_KEY")  

OTEL_EXPORTER_OTLP_ENDPOINT = f"{WANDB_BASE_URL}/otel/v1/traces"
AUTH = base64.b64encode(f"api:{WANDB_API_KEY}".encode()).decode()

OTEL_EXPORTER_OTLP_HEADERS = {
    "Authorization": f"Basic {AUTH}",
    "project_id": PROJECT_ID,
}

# Create the OTLP span exporter with endpoint and headers
exporter = OTLPSpanExporter(
    endpoint=OTEL_EXPORTER_OTLP_ENDPOINT,
    headers=OTEL_EXPORTER_OTLP_HEADERS,
)

# Create a tracer provider and add the exporter
tracer_provider = trace_sdk.TracerProvider()
tracer_provider.add_span_processor(SimpleSpanProcessor(exporter))

# Set the global tracer provider BEFORE importing/using ADK
trace.set_tracer_provider(tracer_provider)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="HW Buddy Backend", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Firebase Admin
if not firebase_admin._apps:
    # Try to use service account key if available, otherwise use default credentials
    try:
        # Look for service account key in various locations
        possible_paths = [
            os.path.join(os.path.dirname(__file__), "hw-buddy-462818-firebase-adminsdk-fbsvc-962e1f8a4a.json"),
            os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", ""),
        ]
        
        cred = None
        for path in possible_paths:
            if path and os.path.exists(path):
                cred = credentials.Certificate(path)
                break
        
        if cred:
            firebase_admin.initialize_app(cred)
        else:
            # Use default credentials (works in Google Cloud environments)
            firebase_admin.initialize_app()
    except Exception as e:
        print(f"Warning: Could not initialize Firebase Admin SDK: {e}")

db = firestore.client()


class ConnectionManager:
    """Manages WebSocket connections for real-time updates"""
    
    def __init__(self):
        # Store active connections by session_id
        self.active_connections: Dict[str, WebSocket] = {}
        # Track running tasks to properly cancel them
        self.active_tasks: Dict[str, asyncio.Task] = {}
    
    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket
        logger.info(f"WebSocket connected for session {session_id}")
    
    def disconnect(self, session_id: str):
        if session_id in self.active_connections:
            del self.active_connections[session_id]
            logger.info(f"WebSocket disconnected for session {session_id}")
        
        # Cancel any running tasks for this session
        if session_id in self.active_tasks:
            task = self.active_tasks[session_id]
            if not task.done():
                task.cancel()
                logger.info(f"Cancelled running task for session {session_id}")
            del self.active_tasks[session_id]
    
    def is_connected(self, session_id: str) -> bool:
        """Check if a session is still connected"""
        if session_id not in self.active_connections:
            return False
        
        websocket = self.active_connections[session_id]
        try:
            # Check if the websocket is still in a valid state
            return websocket.client_state.name in ["CONNECTED", "CONNECTING"]
        except:
            # If we can't check the state, assume disconnected
            self.disconnect(session_id)
            return False
    
    async def send_status_update(self, session_id: str, status: str, data: dict = None):
        """Send a status update to the frontend"""
        if not self.is_connected(session_id):
            logger.warning(f"Cannot send status update to disconnected session {session_id}")
            return
            
        message = {
            "type": "status_update",
            "status": status,
            "data": data or {}
        }
        try:
            await self.active_connections[session_id].send_text(json.dumps(message))
            logger.info(f"Sent status update to session {session_id}: {status}")
        except Exception as e:
            logger.error(f"Error sending status update to session {session_id}: {e}")
            # Remove disconnected connection
            self.disconnect(session_id)
    
    async def send_event_update(self, session_id: str, event_type: str, event_data: dict):
        """Send an ADK event update to the frontend"""
        if not self.is_connected(session_id):
            logger.warning(f"Cannot send ADK event to disconnected session {session_id}")
            return
            
        message = {
            "type": "adk_event",
            "event_type": event_type,
            "data": event_data
        }
        try:
            await self.active_connections[session_id].send_text(json.dumps(message))
            logger.info(f"Sent ADK event to session {session_id}: {event_type}")
        except Exception as e:
            logger.error(f"Error sending ADK event to session {session_id}: {e}")
            # Remove disconnected connection
            self.disconnect(session_id)
    
    async def send_final_response(self, session_id: str, response_data: dict):
        """Send the final response to the frontend"""
        if not self.is_connected(session_id):
            logger.warning(f"Cannot send final response to disconnected session {session_id}")
            return
            
        message = {
            "type": "final_response",
            "data": response_data
        }
        try:
            await self.active_connections[session_id].send_text(json.dumps(message))
            logger.info(f"Sent final response to session {session_id}")
        except Exception as e:
            logger.error(f"Error sending final response to session {session_id}: {e}")
            # Remove disconnected connection
            self.disconnect(session_id)


# Global connection manager instance
connection_manager = ConnectionManager()


class TakePictureRequest(BaseModel):
    session_id: str
    user_ask: Optional[str] = "Please help me with my homework"

class TakePictureResponse(BaseModel):
    success: bool
    message: str
    session_id: str
    image_url: Optional[str] = None
    image_gcs_url: Optional[str] = None
    image_description: Optional[str] = None

@app.get("/")
async def root():
    return {"message": "HW Buddy Backend API"}


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time communication with frontend"""
    await connection_manager.connect(websocket, session_id)
    
    try:
        # Send initial connection confirmation
        await connection_manager.send_status_update(
            session_id, 
            "connected", 
            {"message": "Welcome! Ask me anything about your homework!"}
        )
        
        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Wait for messages from frontend
                data = await websocket.receive_text()
                message = json.loads(data)
                
                # Handle different message types
                if message.get("type") == "process_query":
                    # Cancel any existing task for this session
                    if session_id in connection_manager.active_tasks:
                        old_task = connection_manager.active_tasks[session_id]
                        if not old_task.done():
                            old_task.cancel()
                            logger.info(f"Cancelled previous task for session {session_id}")
                    
                    # Create and track new task
                    task = asyncio.create_task(process_query_websocket(session_id, message.get("user_ask", "")))
                    connection_manager.active_tasks[session_id] = task
                    
                elif message.get("type") == "ping":
                    # Respond to ping to keep connection alive
                    await connection_manager.send_status_update(session_id, "pong", {})
                    
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON received from session {session_id}")
            except Exception as e:
                logger.error(f"Error processing WebSocket message for session {session_id}: {e}")
                break
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error for session {session_id}: {e}")
    finally:
        connection_manager.disconnect(session_id)


async def process_query_websocket(session_id: str, user_ask: str):
    """Process user query and send updates via WebSocket"""
    try:
        # Send initial status
        await connection_manager.send_status_update(
            session_id, 
            "processing_started", 
            {"message": "Starting to process your question..."}
        )
        
        # Get agent and process query
        agent = get_hw_tutor_agent(db, connection_manager)
        
        # Send status update
        await connection_manager.send_status_update(
            session_id, 
            "agent_ready", 
            {"message": "Listening..."}
        )
        
        # Process the query (this will send events through the connection manager)
        agent_result = await agent.process_user_query(
            session_id=session_id,
            user_query=user_ask
        )
        
        # Send final response
        response_data = {
            "success": True,
            "message": f"Request processed successfully for session {session_id}",
            "session_id": session_id,
            "image_url": agent_result.get("image_url"),
            "image_gcs_url": agent_result.get("image_gcs_url"),
            "image_description": agent_result.get("response")
        }
        
        await connection_manager.send_final_response(session_id, response_data)
        
    except Exception as e:
        logger.error(f"Error processing query via WebSocket for session {session_id}: {str(e)}")
        await connection_manager.send_status_update(
            session_id, 
            "error", 
            {"message": f"Error processing request: {str(e)}"}
        )

@app.post("/take_picture", response_model=TakePictureResponse)
async def take_picture(request: TakePictureRequest):
    """
    Process user request using ADK agent which intelligently decides when to take pictures.
    The agent now maintains session state and only takes pictures when contextually relevant.
    """
    logger.info(f"Received take_picture request for session {request.session_id} with query: {request.user_ask}")
    
    try:
        logger.info("Getting HW tutor agent instance...")
        agent = get_hw_tutor_agent(db)
        logger.info("HW tutor agent instance obtained successfully")
        
        logger.info(f"Processing user query through ADK agent for session {request.session_id}")
        # Process the user query through the ADK agent
        # The agent will decide whether to take a picture based on the user's request
        agent_result = await agent.process_user_query(
            session_id=request.session_id,
            user_query=request.user_ask
        )
        logger.info(f"Agent result received: {agent_result}")
        
        response = TakePictureResponse(
            success=True,
            message=f"Request processed successfully for session {request.session_id}",
            session_id=request.session_id,
            image_url=agent_result.get("image_url"),
            image_gcs_url=agent_result.get("image_gcs_url"),
            image_description=agent_result.get("response")
        )
        logger.info(f"Returning successful response for session {request.session_id}")
        return response
            
    except Exception as e:
        logger.error(f"Error processing request for session {request.session_id}: {str(e)}")
        logger.error(f"Full traceback: {traceback.format_exc()}")
        error_message = f"Failed to process request: {str(e)}"
        raise HTTPException(status_code=500, detail=error_message)

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)