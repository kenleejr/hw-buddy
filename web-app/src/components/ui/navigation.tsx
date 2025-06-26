"use client";

import { cn } from "@/lib/utils"
import { Button } from "./button"
import { StatusModal } from "./status-modal"
import { RecordingIndicator } from "./recording-indicator"

interface NavigationProps {
  currentPage?: "hw-buddy" | "parents"
  // Session-specific props (optional)
  sessionId?: string
  status?: string
  error?: string
  audioLevel?: number
  isRecording?: boolean
  onEndSession?: () => void
  onStopRecording?: () => void
}

export function Navigation({ 
  currentPage = "hw-buddy",
  sessionId,
  status,
  error,
  audioLevel,
  isRecording,
  onEndSession,
  onStopRecording
}: NavigationProps) {
  const isInSession = sessionId && status && onEndSession;

  return (
    <nav className="w-full bg-white border-b border-border shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          <div className="flex space-x-8">
            <Button
              variant={currentPage === "hw-buddy" ? "default" : "ghost"}
              className={cn(
                "font-medium",
                currentPage === "hw-buddy" 
                  ? "bg-hw-primary text-white hover:bg-hw-primary/90" 
                  : "text-hw-accent hover:text-hw-primary hover:bg-hw-light"
              )}
            >
              HW Buddy
            </Button>
            <Button
              variant={currentPage === "parents" ? "default" : "ghost"}
              className={cn(
                "font-medium",
                currentPage === "parents" 
                  ? "bg-hw-primary text-white hover:bg-hw-primary/90" 
                  : "text-hw-accent hover:text-hw-primary hover:bg-hw-light"
              )}
            >
              Parents
            </Button>
          </div>
          
          {/* Recording Controls and Status */}
          {isInSession && (
            <div className="flex items-center gap-3">
              {/* Recording Indicator */}
              {onStopRecording && (
                <RecordingIndicator
                  isRecording={isRecording || false}
                  onStopRecording={onStopRecording}
                />
              )}
              
              {/* Status Modal */}
              <StatusModal
                sessionId={sessionId}
                status={status || ""}
                error={error || ""}
                audioLevel={audioLevel || 0}
                isRecording={isRecording || false}
                onEndSession={onEndSession}
              />
            </div>
          )}
        </div>
      </div>
    </nav>
  )
}