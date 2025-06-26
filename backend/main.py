from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import firebase_admin
from firebase_admin import credentials, firestore
import os
import time
import asyncio
from typing import Optional
from google import genai
from google.genai.types import Part, HttpOptions

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

# Initialize Gemini client
def get_gemini_client():
    return genai.Client()

async def analyze_image_with_gemini(image_url: str, user_ask: str = "Please help me with my homework") -> str:
    """
    Analyze an image using Gemini API and return a description of what's in the image,
    specifically focused on homework/educational content.
    """
    try:
        client = get_gemini_client()
        
        # Create content with the image and a prompt for homework analysis
        contents = [
            Part.from_text(text=f"""You are a homework tutor assistant. The student has asked: "{user_ask}" \
                                 
                                 Analyze this image of homework or educational material and provide specific next steps to help the student with their request. \
                                 Focus on answering their question and giving actionable guidance. \
                                 If you see math problems, help solve them step by step. If you see text, help with comprehension or writing. \
                                 Be specific, encouraging, and provide helpful hints without giving away complete answers. \
                                 Your response should directly address what the student is asking for."""
            ),
            Part.from_uri(
                file_uri=image_url,
                mime_type="image/jpeg"
            )
        ]
        
        # Generate content
        response = await client.aio.models.generate_content(
            model='gemini-2.5-flash',
            contents=contents
        )
        
        return response.text
        
    except Exception as e:
        print(f"Error analyzing image with Gemini: {e}")
        return f"I can see an image was captured, but I couldn't analyze its contents due to an error: {str(e)}"

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
    Trigger a picture taking command for the specified session.
    This updates the Firestore document which should trigger the mobile app to take a picture,
    then polls for the resulting image URL.
    """
    try:
        session_ref = db.collection('sessions').document(request.session_id)
        
        # Get the current state to check if there's already an image
        current_doc = session_ref.get()
        current_image_url = None
        if current_doc.exists:
            current_data = current_doc.to_dict()
            current_image_url = current_data.get('last_image_url')
        
        # Update the session document with the take_picture command
        session_ref.update({
            'command': 'take_picture'
        })
        
        # Poll for the image URL update (with timeout)
        max_wait_time = 30  # 30 seconds timeout
        poll_interval = 0.05 # Check every 500ms
        start_time = time.time()
        
        while time.time() - start_time < max_wait_time:
            await asyncio.sleep(poll_interval)
            
            # Check for updated image URL
            updated_doc = session_ref.get()
            if updated_doc.exists:
                updated_data = updated_doc.to_dict()
                new_image_url = updated_data.get('last_image_url')
                
                # If we have a new image URL (different from before)
                if new_image_url and new_image_url != current_image_url:
                    new_image_gcs_url = updated_data.get('last_image_gcs_url')
                    
                    # Analyze the image with Gemini
                    image_description = None
                    try:
                        # Try to use GCS URL first, fallback to HTTP URL
                        url_to_analyze = new_image_gcs_url if new_image_gcs_url else new_image_url
                        image_description = await analyze_image_with_gemini(url_to_analyze, request.user_ask)
                    except Exception as e:
                        print(f"Failed to analyze image: {e}")
                        image_description = "I can see that a picture was taken, but I couldn't analyze its contents."
                    
                    return TakePictureResponse(
                        success=True,
                        message=f"Picture taken and analyzed successfully for session {request.session_id}",
                        session_id=request.session_id,
                        image_url=new_image_url,
                        image_gcs_url=new_image_gcs_url,
                        image_description=image_description
                    )
        
        # If we timeout waiting for the image
        return TakePictureResponse(
            success=False,
            message=f"Timeout waiting for picture from session {request.session_id}",
            session_id=request.session_id,
            image_url=None
        )
    
    except Exception as e:
        error_message = f"Failed to take picture: {str(e)}"
        raise HTTPException(status_code=500, detail=error_message)

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)