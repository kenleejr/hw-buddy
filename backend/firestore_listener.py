import asyncio
import time
from typing import Optional, Dict, Any
import firebase_admin
from firebase_admin import firestore
import threading
from concurrent.futures import ThreadPoolExecutor


class FirestoreListener:
    """
    Firestore real-time listener to replace inefficient polling.
    Uses Firestore's native real-time capabilities for immediate updates.
    """
    
    def __init__(self, db_client=None):
        self.db = db_client or firestore.client()
        self.active_listeners = {}
        self.executor = ThreadPoolExecutor(max_workers=10)
    
    async def wait_for_image_update(
        self, 
        session_id: str, 
        timeout: int = 30,
        current_image_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Wait for image update using real-time Firestore listener.
        
        Args:
            session_id: Session document ID to watch
            timeout: Maximum wait time in seconds
            current_image_url: Current image URL to detect changes
            
        Returns:
            Dictionary with updated session data
            
        Raises:
            Exception: If timeout is reached or other errors
        """
        
        # Use a future to handle the async result
        future = asyncio.Future()
        listener = None
        
        def on_snapshot(doc_snapshot, changes, read_time):
            """Callback when document changes"""
            try:
                for doc in doc_snapshot:
                    if not doc.exists:
                        if not future.done():
                            future.set_exception(Exception("Session document not found"))
                        return
                    
                    data = doc.to_dict()
                    
                    # Check if image was updated
                    new_image_url = data.get('last_image_url')
                    command = data.get('command')
                    
                    # Image processing completed when:
                    # 1. Command is 'done' AND
                    # 2. We have a new image URL AND 
                    # 3. It's different from current URL (if provided)
                    if (command == 'done' and 
                        new_image_url and 
                        new_image_url != current_image_url):
                        
                        if not future.done():
                            # Schedule the result to be set in the event loop
                            asyncio.get_event_loop().call_soon_threadsafe(
                                lambda: future.set_result(data) if not future.done() else None
                            )
                            
            except Exception as e:
                if not future.done():
                    asyncio.get_event_loop().call_soon_threadsafe(
                        lambda: future.set_exception(e) if not future.done() else None
                    )
        
        try:
            # Set up real-time listener
            doc_ref = self.db.collection('sessions').document(session_id)
            
            # Check if document exists first
            doc = doc_ref.get()
            if not doc.exists:
                raise Exception(f"Session {session_id} not found")
            
            # Start listening for changes
            listener = doc_ref.on_snapshot(on_snapshot)
            
            # Store listener for cleanup
            self.active_listeners[session_id] = listener
            
            # Wait for result with timeout
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
            
        except asyncio.TimeoutError:
            raise Exception(f"Timeout waiting for image update from session {session_id}")
        except Exception as e:
            raise Exception(f"Error waiting for image update: {str(e)}")
        finally:
            # Clean up listener
            if listener:
                listener.unsubscribe()
            if session_id in self.active_listeners:
                del self.active_listeners[session_id]
    
    def cleanup_all_listeners(self):
        """Clean up all active listeners"""
        for listener in self.active_listeners.values():
            if listener:
                listener.unsubscribe()
        self.active_listeners.clear()
    
    async def close(self):
        """Close the client and clean up resources"""
        self.cleanup_all_listeners()
        self.executor.shutdown(wait=True)


# Global instance for reuse across requests
firestore_listener = None

def get_firestore_listener(db_client=None):
    """Get or create global firestore listener instance"""
    global firestore_listener
    if firestore_listener is None:
        firestore_listener = FirestoreListener(db_client)
    return firestore_listener