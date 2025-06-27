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
from firestore_listener import get_firestore_listener

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
            Part.from_text(text=f"""You are a math homework tutor assistant. The student has asked: "{user_ask}" \
                                 
                                 Analyze this image of math homework or educational material. \
                                 1. Convert the main content of what the student is asking about into MathJax syntax, including their current progress. Add a comment inline with their progress with a pointer. \
                                 2. Write down some BRIEF pointers or helpers to aid the student in their progress. Be specific, encouraging, and provide helpful hints without giving away complete answers.
                                                      
                                IMPORTANT: For the mathjax_content, use proper MathJax formatting:
                                - Use $$...$$ for display math (equations on their own lines)  
                                - Put each equation on consecutive lines with NO blank lines between them
                                - Do NOT use \\n or \\\\ or double line breaks
                                - Example format (no empty lines between):
                                $$equation1$$
                                $$equation2$$
                                $$equation3$$
                                
                                Respond with the following JSON format:
                                {{
                                    "mathjax_content": <math_jax_content_with_proper_line_breaks>,
                                    "help_text": <help_text>
                                }}
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

        # Clean and parse the JSON response
        raw_text = response.text.strip()
        
        # Remove common markdown formatting that LLMs add
        if raw_text.startswith('```json'):
            raw_text = raw_text[7:]  # Remove ```json
        if raw_text.startswith('```'):
            raw_text = raw_text[3:]   # Remove ```
        if raw_text.endswith('```'):
            raw_text = raw_text[:-3]  # Remove trailing ```
        
        raw_text = raw_text.strip()
        
        print(raw_text)
        try:
            # Try to parse as JSON
            import json
            parsed_response = json.loads(raw_text)
            
            # Validate expected structure
            if isinstance(parsed_response, dict) and "mathjax_content" in parsed_response and "help_text" in parsed_response:
                return json.dumps(parsed_response)  # Return clean JSON string
            else:
                # Fallback if structure is unexpected
                return json.dumps({
                    "mathjax_content": "",
                    "help_text": raw_text
                })
        except json.JSONDecodeError:
            # If JSON parsing fails, return the raw text as help_text
            return json.dumps({
                "mathjax_content": "",
                "help_text": raw_text
            })
        
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
    This updates the Firestore document which triggers the mobile app to take a picture,
    then uses real-time listeners for immediate response when image is ready.
    """
    try:
        session_ref = db.collection('sessions').document(request.session_id)
        
        # Get the current state to check if there's already an image
        current_doc = session_ref.get()
        current_image_url = None
        if current_doc.exists:
            current_data = current_doc.to_dict()
            current_image_url = current_data.get('last_image_url')
        else:
            return TakePictureResponse(
                success=False,
                message=f"Session {request.session_id} not found",
                session_id=request.session_id,
                image_url=None
            )
        
        # Update the session document with the take_picture command
        session_ref.update({
            'command': 'take_picture'
        })
        
        # Use real-time listener instead of polling (much more efficient)
        try:
            listener = get_firestore_listener(db)
            updated_data = await listener.wait_for_image_update(
                session_id=request.session_id,
                timeout=30,
                current_image_url=current_image_url
            )
            
            new_image_url = updated_data.get('last_image_url')
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
            
        except Exception as listener_error:
            # Handle timeout or other listener errors
            return TakePictureResponse(
                success=False,
                message=f"Error waiting for picture: {str(listener_error)}",
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