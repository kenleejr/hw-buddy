"""
Simple test script to debug the take_picture functionality.
This uses a real Firebase connection but with a test session ID.
"""

import asyncio
import logging
import sys
import os

# Add parent directory to Python path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hw_tutor_agent import get_hw_tutor_agent
import firebase_admin
from firebase_admin import credentials, firestore

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_take_picture_simple():
    """Simple test to see if the agent calls take_picture."""
    
    logger.info("🧪 Starting simple take_picture test...")
    
    try:
        # Initialize Firebase if not already done
        if not firebase_admin._apps:
            # Try to use service account key if available
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
                logger.info("Firebase initialized with service account")
            else:
                firebase_admin.initialize_app()
                logger.info("Firebase initialized with default credentials")
        
        db = firestore.client()
        logger.info("Firestore client created")
        
        # Create a test session in Firestore first
        test_session_id = "test_session_simple_123"
        logger.info(f"Using test session ID: {test_session_id}")
        
        # Create/update the test session document
        session_ref = db.collection('sessions').document(test_session_id)
        session_ref.set({
            'session_id': test_session_id,
            'status': 'active',
            'created_at': firestore.SERVER_TIMESTAMP,
            'last_image_url': 'https://example.com/test_initial.jpg'  # Initial image
        })
        logger.info("Test session document created in Firestore")
        
        # Get the agent
        agent = get_hw_tutor_agent(db)
        logger.info("HW Tutor Agent obtained")
        
        # Test different queries to see which ones trigger take_picture
        test_queries = [
            "Can you help me check my math homework?",
            "Please look at my work and tell me if it's correct",
            "I need help solving this problem",
            "Can you take a picture of my homework?",
            "Check my work please"
        ]
        
        for i, query in enumerate(test_queries):
            logger.info(f"\n{'='*50}")
            logger.info(f"🔍 TEST {i+1}: {query}")
            logger.info(f"{'='*50}")
            
            try:
                result = await agent.process_user_query(
                    session_id=test_session_id,
                    user_query=query
                )
                
                logger.info(f"✅ Query processed successfully")
                logger.info(f"Result type: {type(result)}")
                logger.info(f"Result: {result}")
                
                # Check if take_picture was called
                if isinstance(result, dict):
                    image_url = result.get("image_url")
                    image_gcs_url = result.get("image_gcs_url")
                    response = result.get("response")
                    
                    if image_url or image_gcs_url:
                        logger.info("🎉 SUCCESS: take_picture function was called!")
                        logger.info(f"   Image URL: {image_url}")
                        logger.info(f"   GCS URL: {image_gcs_url}")
                    else:
                        logger.warning("⚠️  take_picture function was NOT called")
                    
                    logger.info(f"Response: {response}")
                else:
                    logger.error(f"❌ Unexpected result type: {type(result)}")
                
            except Exception as query_error:
                logger.error(f"❌ Error processing query: {query_error}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Clean up test session
        session_ref.delete()
        logger.info("Test session cleaned up")
        
    except Exception as e:
        logger.error(f"❌ Test setup failed: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    asyncio.run(test_take_picture_simple())