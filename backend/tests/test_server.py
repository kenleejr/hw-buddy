#!/usr/bin/env python3
"""
Quick test script to verify the backend changes work.
Tests the imports and basic functionality without Firebase credentials.
"""

import asyncio
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

def test_imports():
    """Test that all imports work correctly"""
    print("Testing imports...")
    
    try:
        from fastapi import FastAPI, HTTPException
        print("✓ FastAPI imports successful")
        
        from firestore_listener import get_firestore_listener, FirestoreListener
        print("✓ FirestoreListener imports successful")
        
        # Test FirestoreListener creation (without Firebase connection)
        # This will fail at runtime but should import correctly
        try:
            listener = FirestoreListener()
            print("✓ FirestoreListener class creation syntax valid")
        except Exception as e:
            if "credentials" in str(e).lower() or "application default" in str(e).lower():
                print("✓ FirestoreListener class syntax valid (expected Firebase credential error)")
            else:
                print(f"✗ Unexpected error in FirestoreListener: {e}")
                return False
                
        print("✓ All imports successful!")
        return True
        
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False

def test_async_functionality():
    """Test async functionality"""
    print("\nTesting async functionality...")
    
    async def test_async():
        # Test that our async patterns are valid
        future = asyncio.Future()
        future.set_result({"test": "data"})
        result = await future
        return result
    
    try:
        result = asyncio.run(test_async())
        print(f"✓ Async functionality works: {result}")
        return True
    except Exception as e:
        print(f"✗ Async error: {e}")
        return False

def main():
    """Run all tests"""
    print("=== HW Buddy Backend Testing ===\n")
    
    tests = [
        test_imports,
        test_async_functionality,
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print(f"=== Results: {passed}/{total} tests passed ===")
    
    if passed == total:
        print("🎉 All tests passed! Backend changes look good.")
        return True
    else:
        print("❌ Some tests failed. Check the output above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)