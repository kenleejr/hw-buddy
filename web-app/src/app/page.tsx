"use client";

import { useState } from "react";
import Image from "next/image";
import { GeminiLiveSession } from "./components/GeminiLiveSession";
import { Navigation } from "@/components/ui/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

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
              
              <Button
                type="submit"
                className="w-full bg-hw-primary hover:bg-hw-primary/90 text-white font-medium text-lg h-12"
              >
                Start Session
              </Button>
            </form>
          </CardContent>
        </Card>
      </main>
    </div>
  );
}