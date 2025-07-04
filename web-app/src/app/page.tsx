"use client";

import { useState, useEffect } from "react";
import Image from "next/image";
import QRCode from "react-qr-code";
import { WebSocketGeminiSession } from "./components/WebSocketGeminiSession";
import { Navigation } from "@/components/ui/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

export default function Home() {
  const [sessionId, setSessionId] = useState("");
  const [isSessionActive, setIsSessionActive] = useState(false);
  const [showManualEntry, setShowManualEntry] = useState(false);

  // Generate session ID automatically when component mounts
  useEffect(() => {
    if (!sessionId) {
      const newSessionId = generateSessionId();
      setSessionId(newSessionId);
    }
  }, []);

  const generateSessionId = () => {
    return 'session_' + Math.random().toString(36).substr(2, 9);
  };

  const handleStartSession = () => {
    setIsSessionActive(true);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (sessionId.trim()) {
      setIsSessionActive(true);
    }
  };

  const handleEndSession = () => {
    setIsSessionActive(false);
    const newSessionId = generateSessionId();
    setSessionId(newSessionId);
  };

  if (isSessionActive) {
    return (
      <WebSocketGeminiSession 
        sessionId={sessionId}
        onEndSession={handleEndSession}
      />
    );
  }

  return (
    <div className="min-h-screen bg-hw-light">
      <Navigation currentPage="hw-buddy" />
      
      <main className="flex items-center justify-center p-4 pt-16">
        <Card className="max-w-md w-full shadow-lg">
          <CardHeader className="text-center pb-4">
            <div className="flex justify-center mb-6">
              <Image
                src="/hw_buddy_logo.png"
                alt="Homework Buddy Logo"
                width={200}
                height={200}
                className="rounded-lg"
                priority
              />
            </div>
            <CardTitle className="text-3xl font-bold text-hw-primary">
              Welcome to Homework Buddy
            </CardTitle>
          </CardHeader>
          
          <CardContent>
            {!showManualEntry ? (
              <div className="space-y-6">
                <div className="text-center">
                  <p className="text-sm font-medium text-hw-accent mb-4">
                    Scan this QR code with your mobile device to connect
                  </p>
                  <div className="flex justify-center mb-4">
                    <div className="bg-white p-4 rounded-lg shadow-sm">
                      <QRCode
                        value={sessionId}
                        size={200}
                        level="M"
                        className="border"
                      />
                    </div>
                  </div>
                  <p className="text-xs text-gray-500 mb-2">
                    Session ID: {sessionId}
                  </p>
                  <button
                    onClick={() => setShowManualEntry(true)}
                    className="text-xs text-hw-primary hover:underline"
                  >
                    Enter session ID manually instead
                  </button>
                </div>
                
                <Button
                  onClick={handleStartSession}
                  className="w-full bg-hw-primary hover:bg-hw-primary/90 text-white font-medium text-lg h-12"
                >
                  Start Session
                </Button>
              </div>
            ) : (
              <form onSubmit={handleSubmit} className="space-y-6">
                <div className="space-y-2">
                  <label 
                    htmlFor="sessionId" 
                    className="block text-sm font-medium text-hw-accent text-center"
                  >
                    Enter Session ID
                  </label>
                  <Input
                    type="text"
                    id="sessionId"
                    value={sessionId}
                    onChange={(e) => setSessionId(e.target.value)}
                    className="text-center border-2 focus:border-hw-primary"
                    placeholder="Session ID"
                    required
                  />
                </div>
                
                <div className="space-y-2">
                  <Button
                    type="submit"
                    className="w-full bg-hw-primary hover:bg-hw-primary/90 text-white font-medium text-lg h-12"
                  >
                    Start Session
                  </Button>
                  <button
                    type="button"
                    onClick={() => setShowManualEntry(false)}
                    className="w-full text-xs text-hw-primary hover:underline"
                  >
                    Back to QR code
                  </button>
                </div>
              </form>
            )}
          </CardContent>
        </Card>
      </main>
    </div>
  );
}