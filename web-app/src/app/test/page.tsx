"use client";

import { useState, useEffect } from 'react';
import { BackendAudioClient, BackendMessage } from '../utils/backendAudioClient';

export default function TestPage() {
  const [connectionStatus, setConnectionStatus] = useState('disconnected');
  const [messages, setMessages] = useState<string[]>([]);
  const [audioLevel, setAudioLevel] = useState(0);
  const [isRecording, setIsRecording] = useState(false);
  const [sessionId] = useState('test-session-' + Date.now());

  const addMessage = (message: string) => {
    setMessages(prev => [...prev.slice(-9), `${new Date().toLocaleTimeString()}: ${message}`]);
  };

  const testConnection = async () => {
    try {
      addMessage('Creating audio client...');
      
      const audioClient = new BackendAudioClient();
      
      audioClient.onConnectionChange = (connected) => {
        setConnectionStatus(connected ? 'connected' : 'disconnected');
        addMessage(`Connection ${connected ? 'established' : 'lost'}`);
      };
      
      audioClient.onMessage = (message: BackendMessage) => {
        addMessage(`Backend: ${message.type} - ${JSON.stringify(message.data)}`);
      };
      
      audioClient.onAudioLevel = (level) => {
        setAudioLevel(level);
      };
      
      audioClient.onError = (error) => {
        addMessage(`Error: ${error}`);
      };

      addMessage('Connecting to backend...');
      await audioClient.connect(sessionId);
      
      // Test recording
      window.testAudioClient = audioClient;
      addMessage('Audio client ready. Use browser console: window.testAudioClient');
      
    } catch (error) {
      addMessage(`Connection failed: ${error}`);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-3xl font-bold mb-8">HW Buddy Backend Audio Test</h1>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Connection Test */}
          <div className="bg-white p-6 rounded-lg shadow-md">
            <h2 className="text-xl font-semibold mb-4">Connection Test</h2>
            
            <div className="space-y-4">
              <div className="flex items-center space-x-2">
                <span className="font-medium">Status:</span>
                <span className={`px-2 py-1 rounded text-sm ${
                  connectionStatus === 'connected' 
                    ? 'bg-green-100 text-green-800' 
                    : 'bg-red-100 text-red-800'
                }`}>
                  {connectionStatus}
                </span>
              </div>
              
              <div className="flex items-center space-x-2">
                <span className="font-medium">Session ID:</span>
                <span className="text-sm text-gray-600">{sessionId}</span>
              </div>
              
              <button
                onClick={testConnection}
                className="w-full bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded"
              >
                Test Backend Connection
              </button>
            </div>
          </div>

          {/* Audio Level */}
          <div className="bg-white p-6 rounded-lg shadow-md">
            <h2 className="text-xl font-semibold mb-4">Audio Level</h2>
            
            <div className="space-y-4">
              <div className="flex items-center space-x-2">
                <span className="font-medium">Level:</span>
                <span className="text-sm">{audioLevel.toFixed(1)}%</span>
              </div>
              
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div 
                  className="bg-blue-600 h-2 rounded-full transition-all duration-100"
                  style={{ width: `${Math.min(audioLevel, 100)}%` }}
                />
              </div>
              
              <p className="text-sm text-gray-600">
                Audio level will show when recording starts
              </p>
            </div>
          </div>
        </div>

        {/* Message Log */}
        <div className="mt-6 bg-white p-6 rounded-lg shadow-md">
          <h2 className="text-xl font-semibold mb-4">Message Log</h2>
          
          <div className="bg-gray-900 text-green-400 p-4 rounded font-mono text-sm max-h-96 overflow-y-auto">
            {messages.length === 0 ? (
              <div className="text-gray-500">Click "Test Backend Connection" to start...</div>
            ) : (
              messages.map((message, index) => (
                <div key={index} className="mb-1">{message}</div>
              ))
            )}
          </div>
        </div>

        {/* Instructions */}
        <div className="mt-6 bg-blue-50 p-6 rounded-lg">
          <h2 className="text-xl font-semibold mb-4 text-blue-800">Test Instructions</h2>
          
          <div className="space-y-2 text-blue-700">
            <p><strong>1.</strong> Make sure the backend server is running on port 8000</p>
            <p><strong>2.</strong> Click "Test Backend Connection" to establish WebSocket connection</p>
            <p><strong>3.</strong> Open browser console to access window.testAudioClient</p>
            <p><strong>4.</strong> Test recording: <code>window.testAudioClient.startRecording()</code></p>
            <p><strong>5.</strong> Stop recording: <code>window.testAudioClient.stopRecording()</code></p>
          </div>
          
          <div className="mt-4 p-3 bg-yellow-100 rounded border border-yellow-300">
            <p className="text-yellow-800 text-sm">
              <strong>Note:</strong> This is a test page for verifying backend integration. 
              The main app is available at <a href="/" className="underline">the home page</a>.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}