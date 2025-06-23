"use client";

import { useState } from "react";
import { GeminiLiveSession } from "./components/GeminiLiveSession";

export default function Home() {
  const [sessionId, setSessionId] = useState("");
  const [isSessionActive, setIsSessionActive] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (sessionId.trim()) {
      setIsSessionActive(true);
    }
  };

  const handleEndSession = () => {
    setIsSessionActive(false);
    setSessionId("");
  };

  if (isSessionActive) {
    return (
      <GeminiLiveSession 
        sessionId={sessionId}
        onEndSession={handleEndSession}
      />
    );
  }

  return (
    <main className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-white rounded-lg shadow-lg p-8">
        <h1 className="text-3xl font-bold text-center text-gray-800 mb-8">
          Homework Buddy
        </h1>
        
        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label 
              htmlFor="sessionId" 
              className="block text-sm font-medium text-gray-700 mb-2 text-center"
            >
              Enter Session ID
            </label>
            <input
              type="text"
              id="sessionId"
              value={sessionId}
              onChange={(e) => setSessionId(e.target.value)}
              className="w-full px-4 py-3 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-center"
              placeholder="Session ID"
              required
            />
          </div>
          
          <button
            type="submit"
            className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-3 px-4 rounded-md transition duration-200 ease-in-out transform hover:scale-105"
          >
            Start Session
          </button>
        </form>
      </div>
    </main>
  );
}