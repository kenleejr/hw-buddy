'use client';

import { useState, useEffect } from 'react';
import { doc, updateDoc, onSnapshot } from 'firebase/firestore';
import { db } from '@/lib/firebase';

interface TakePictureProps {
  sessionId: string;
}

export default function TakePicture({ sessionId }: TakePictureProps) {
  const [isLoading, setIsLoading] = useState(false);
  const [currentImageUrl, setCurrentImageUrl] = useState<string | null>(null);

  useEffect(() => {
    const sessionRef = doc(db, 'sessions', sessionId);
    const unsubscribe = onSnapshot(sessionRef, (doc) => {
      if (doc.exists()) {
        const data = doc.data();
        if (data.last_image_url) {
          setCurrentImageUrl(data.last_image_url);
        }
      }
    });

    return () => unsubscribe();
  }, [sessionId]);

  const handleTakePicture = async () => {
    setIsLoading(true);
    try {
      const sessionRef = doc(db, 'sessions', sessionId);
      await updateDoc(sessionRef, {
        command: 'take_picture'
      });
    } catch (error) {
      console.error('Error updating session:', error);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-400 via-pink-500 to-red-500 flex items-center justify-center">
      <div className="bg-white rounded-lg shadow-xl p-8 max-w-md w-full mx-4">
        <h1 className="text-2xl font-bold text-gray-800 text-center mb-8">
          Session: {sessionId}
        </h1>
        
        {currentImageUrl && (
          <div className="mb-6 flex justify-center">
            <img 
              src={currentImageUrl} 
              alt="Latest captured image"
              className="max-w-full max-h-64 rounded-lg shadow-md"
            />
          </div>
        )}
        
        <div className="flex justify-center">
          <button
            onClick={handleTakePicture}
            disabled={isLoading}
            className="bg-blue-500 hover:bg-blue-600 disabled:bg-blue-300 text-white font-bold py-4 px-8 rounded-lg text-lg transition-colors duration-200"
          >
            {isLoading ? 'Taking Picture...' : 'Take Picture'}
          </button>
        </div>
      </div>
    </div>
  );
}