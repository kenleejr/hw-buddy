"use client";

import { Button } from "./button";

interface RecordingIndicatorProps {
  isRecording: boolean;
  onStopRecording: () => void;
}

export function RecordingIndicator({ isRecording, onStopRecording }: RecordingIndicatorProps) {
  if (!isRecording) return null;

  return (
    <div className="flex items-center gap-2">
      <div className="flex items-center gap-1">
        <div className="w-2 h-2 bg-red-500 rounded-full animate-pulse"></div>
        <span className="text-xs text-red-600 font-medium">Recording</span>
      </div>
      <Button
        onClick={onStopRecording}
        variant="outline"
        size="sm"
        className="h-7 px-2 text-xs text-red-600 border-red-200 hover:bg-red-50"
      >
        <div className="w-2 h-2 bg-red-500 rounded-sm mr-1"></div>
        Stop
      </Button>
    </div>
  );
}