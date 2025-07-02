from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import firebase_admin
from firebase_admin import credentials, firestore
import os
import logging
import traceback
from typing import Optional
# from hw_tutor_agent import get_hw_tutor_agent  # No longer needed

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

class CaptureImageRequest(BaseModel):
    session_id: str
    user_question: str
    context: Optional[str] = ""

class TakePictureResponse(BaseModel):
    success: bool
    message: str
    session_id: str
    image_url: Optional[str] = None
    image_gcs_url: Optional[str] = None
    image_description: Optional[str] = None

class CaptureImageResponse(BaseModel):
    success: bool
    message: str
    session_id: str
    image_url: Optional[str] = None
    image_gcs_url: Optional[str] = None
    image_data: Optional[str] = None  # Base64 encoded image data

@app.get("/")
async def root():
    return {"message": "HW Buddy Backend API"}

@app.post("/capture_image", response_model=CaptureImageResponse)
async def capture_image(request: CaptureImageRequest):
    """
    Simplified image capture endpoint that triggers mobile camera and returns image data.
    No AI processing - just pure image capture for Gemini Live to analyze.
    """
    logger.info(f"Received capture_image request for session {request.session_id} with question: {request.user_question}")
    
    try:
        # Trigger mobile camera via Firestore
        session_ref = db.collection('sessions').document(request.session_id)
        
        logger.info(f"Triggering camera capture for session {request.session_id}")
        
        # Send command to mobile app to take picture
        session_ref.update({
            'command': 'take_picture',
            'user_question': request.user_question,
            'context': request.context,
            'timestamp': firestore.SERVER_TIMESTAMP
        })
        
        # Wait for mobile app to upload image (polling approach)
        import asyncio
        import time
        
        max_wait_time = 15  # seconds
        poll_interval = 0.5  # seconds
        start_time = time.time()
        
        while time.time() - start_time < max_wait_time:
            # Check if image has been uploaded
            session_doc = session_ref.get()
            if session_doc.exists:
                session_data = session_doc.to_dict()
                
                if session_data.get('latest_image_url') and session_data.get('latest_image_gcs_url'):
                    logger.info(f"Image captured successfully for session {request.session_id}")
                    
                    # Get base64 image data if available
                    image_data = session_data.get('latest_image_data')  # Base64 encoded
                    
                    response = CaptureImageResponse(
                        success=True,
                        message=f"Image captured successfully for session {request.session_id}",
                        session_id=request.session_id,
                        image_url=session_data.get('latest_image_url'),
                        image_gcs_url=session_data.get('latest_image_gcs_url'),
                        image_data=image_data
                    )
                    logger.info(f"Returning successful image capture response for session {request.session_id}")
                    return response
            
            await asyncio.sleep(poll_interval)
        
        # Timeout - no image received
        logger.warning(f"Timeout waiting for image capture for session {request.session_id}")
        response = CaptureImageResponse(
            success=False,
            message=f"Timeout waiting for image capture",
            session_id=request.session_id
        )
        return response
            
    except Exception as e:
        logger.error(f"Error capturing image for session {request.session_id}: {str(e)}")
        logger.error(f"Full traceback: {traceback.format_exc()}")
        error_message = f"Failed to capture image: {str(e)}"
        raise HTTPException(status_code=500, detail=error_message)

@app.post("/take_picture", response_model=TakePictureResponse)
async def take_picture(request: TakePictureRequest):
    """
    Legacy endpoint - kept for backward compatibility
    """
    logger.info(f"Legacy take_picture endpoint called - redirecting to capture_image")
    
    # Convert to new request format
    capture_request = CaptureImageRequest(
        session_id=request.session_id,
        user_question=request.user_ask or "Please help me with my homework"
    )
    
    # Call the new endpoint
    capture_result = await capture_image(capture_request)
    
    # Convert response back to legacy format
    response = TakePictureResponse(
        success=capture_result.success,
        message=capture_result.message,
        session_id=capture_result.session_id,
        image_url=capture_result.image_url,
        image_gcs_url=capture_result.image_gcs_url,
        image_description=None  # No AI analysis in simplified version
    )
    
    return response

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)