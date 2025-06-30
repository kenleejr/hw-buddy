from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import firebase_admin
from firebase_admin import credentials, firestore
import os
import logging
import traceback
from typing import Optional
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