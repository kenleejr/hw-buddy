"use client";

import * as React from "react";
import { Button } from "./button";
import { Card, CardContent, CardHeader, CardTitle } from "./card";

interface StatusModalProps {
  sessionId: string;
  status: string;
  error: string;
  audioLevel: number;
  isRecording: boolean;
  onEndSession: () => void;
}

export function StatusModal({ 
  sessionId, 
  status, 
  error, 
  audioLevel, 
  isRecording, 
  onEndSession 
}: StatusModalProps) {
  const [isOpen, setIsOpen] = React.useState(false);

  return (
    <div className="relative">
      {/* Status Indicator Button */}
      <Button
        variant="ghost"
        size="sm"
        onClick={() => setIsOpen(!isOpen)}
        className={`text-xs ${error ? 'text-red-600' : isRecording ? 'text-green-600' : 'text-hw-accent'}`}
      >
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${error ? 'bg-red-500' : isRecording ? 'bg-green-500 animate-pulse' : 'bg-hw-accent'}`}></div>
          Session
        </div>
      </Button>

      {/* Dropdown Modal */}
      {isOpen && (
        <>
          {/* Backdrop */}
          <div className="fixed inset-0 z-40" onClick={() => setIsOpen(false)} />
          
          {/* Modal Content */}
          <Card className="absolute right-0 top-full mt-2 w-80 z-50 shadow-lg">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium text-hw-primary">
                Session Information
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div>
                <span className="text-xs font-medium text-hw-accent">Session ID:</span>
                <div className="text-sm text-foreground font-mono">{sessionId}</div>
              </div>
              
              <div>
                <span className="text-xs font-medium text-hw-accent">Status:</span>
                <div className={`text-sm ${error ? 'text-red-600' : 'text-green-600'}`}>
                  {error || status}
                </div>
              </div>
              
              {isRecording && (
                <div>
                  <span className="text-xs font-medium text-hw-accent">Microphone Level:</span>
                  <div className="mt-1">
                    <div className="w-full h-2 bg-hw-light rounded-full overflow-hidden border">
                      <div 
                        className="h-full bg-green-500 transition-all duration-100"
                        style={{ width: `${Math.min(audioLevel * 10, 100)}%` }}
                      />
                    </div>
                    <div className="text-xs text-hw-accent mt-1">
                      Level: {audioLevel.toFixed(2)}
                    </div>
                  </div>
                </div>
              )}
              
              <div className="pt-2 border-t border-border">
                <Button
                  onClick={onEndSession}
                  variant="outline"
                  size="sm"
                  className="w-full text-red-600 border-red-200 hover:bg-red-50"
                >
                  End Session
                </Button>
              </div>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}