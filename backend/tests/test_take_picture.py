"""
Unit test for the take_picture functionality in the HW Buddy backend.
This test helps debug why the agent isn't calling the take_picture function.
"""

import asyncio
import logging
import pytest
import sys
import os
from unittest.mock import MagicMock, AsyncMock, patch

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hw_tutor_agent import HWTutorAgent
from firebase_admin import firestore

# Configure logging for the test
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

@pytest.fixture
def mock_firestore():
    """Create a mock Firestore client."""
    mock_db = MagicMock(spec=firestore.Client)
    
    # Mock session document
    mock_doc = MagicMock()
    mock_doc.exists = True
    mock_doc.to_dict.return_value = {
        'last_image_url': 'https://example.com/old_image.jpg',
        'last_image_gcs_url': 'gs://bucket/old_image.jpg'
    }
    
    mock_session_ref = MagicMock()
    mock_session_ref.get.return_value = mock_doc
    mock_session_ref.update = MagicMock()
    
    mock_db.collection.return_value.document.return_value = mock_session_ref
    
    return mock_db

@pytest.fixture
def mock_firestore_listener():
    """Mock the firestore listener."""
    with patch('hw_tutor_agent.get_firestore_listener') as mock_listener_factory:
        mock_listener = AsyncMock()
        mock_listener.wait_for_image_update.return_value = {
            'last_image_url': 'https://example.com/new_image.jpg',
            'last_image_gcs_url': 'gs://bucket/new_image.jpg'
        }
        mock_listener_factory.return_value = mock_listener
        yield mock_listener

@pytest.mark.asyncio
async def test_take_picture_agent_call():
    """Test that the agent calls the take_picture function when it should."""
    
    # Create a mock Firestore client
    mock_db = MagicMock(spec=firestore.Client)
    
    # Mock session document
    mock_doc = MagicMock()
    mock_doc.exists = True
    mock_doc.to_dict.return_value = {
        'last_image_url': 'https://example.com/old_image.jpg',
        'last_image_gcs_url': 'gs://bucket/old_image.jpg'
    }
    
    mock_session_ref = MagicMock()
    mock_session_ref.get.return_value = mock_doc
    mock_session_ref.update = MagicMock()
    
    mock_db.collection.return_value.document.return_value = mock_session_ref
    
    # Mock the firestore listener
    with patch('hw_tutor_agent.get_firestore_listener') as mock_listener_factory:
        mock_listener = AsyncMock()
        mock_listener.wait_for_image_update.return_value = {
            'last_image_url': 'https://example.com/new_image.jpg',
            'last_image_gcs_url': 'gs://bucket/new_image.jpg'
        }
        mock_listener_factory.return_value = mock_listener
        
        # Create the agent
        logger.info("Creating HWTutorAgent...")
        agent = HWTutorAgent(mock_db)
        logger.info("Agent created successfully")
        
        # Test query that should trigger take_picture
        test_session_id = "test_session_123"
        test_query = "Can you check my math homework and help me solve this problem?"
        
        logger.info(f"Testing with session_id: {test_session_id}")
        logger.info(f"Testing with query: {test_query}")
        
        # Process the query
        try:
            result = await agent.process_user_query(
                session_id=test_session_id,
                user_query=test_query
            )
            
            logger.info(f"Result received: {result}")
            
            # Verify the result structure
            assert isinstance(result, dict), f"Expected dict, got {type(result)}"
            assert "response" in result, "Response should contain 'response' key"
            assert "image_url" in result, "Response should contain 'image_url' key"
            assert "image_gcs_url" in result, "Response should contain 'image_gcs_url' key"
            
            # Check if image URLs are present (indicating take_picture was called)
            if result["image_url"] and result["image_gcs_url"]:
                logger.info("✅ SUCCESS: take_picture function was called - image URLs present")
                logger.info(f"Image URL: {result['image_url']}")
                logger.info(f"GCS URL: {result['image_gcs_url']}")
                
                # Verify the mock was called
                mock_session_ref.update.assert_called_with({'command': 'take_picture'})
                mock_listener.wait_for_image_update.assert_called_once()
                
            else:
                logger.error("❌ FAILURE: take_picture function was NOT called - no image URLs")
                logger.error("This suggests the agent is not recognizing the need to take a picture")
            
            # Log the response text
            logger.info(f"Agent response text: {result['response']}")
            
            return result
            
        except Exception as e:
            logger.error(f"Test failed with exception: {str(e)}")
            logger.error(f"Exception type: {type(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

def test_agent_tool_creation():
    """Test that the agent and tools are created correctly."""
    
    mock_db = MagicMock(spec=firestore.Client)
    
    logger.info("Testing agent creation...")
    agent = HWTutorAgent(mock_db)
    
    # Verify agent components
    assert agent.agent is not None, "LlmAgent should be created"
    assert agent.take_picture_tool is not None, "take_picture tool should be created"
    assert agent.runner is not None, "Runner should be created"
    
    # Verify tool is registered with agent
    assert len(agent.agent.tools) > 0, "Agent should have tools registered"
    assert agent.take_picture_tool in agent.agent.tools, "take_picture tool should be in agent tools"
    
    logger.info("✅ Agent creation test passed")

if __name__ == "__main__":
    # Run the async test directly
    async def main():
        logger.info("Starting take_picture test...")
        try:
            await test_take_picture_agent_call()
            logger.info("Test completed successfully!")
        except Exception as e:
            logger.error(f"Test failed: {e}")
    
    # Also run the sync test
    test_agent_tool_creation()
    
    # Run the async test
    asyncio.run(main())