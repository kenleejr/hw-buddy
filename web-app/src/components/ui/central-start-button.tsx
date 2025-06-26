"use client";

import Image from "next/image";
import { Button } from "./button";

interface CentralStartButtonProps {
  isRecording: boolean;
  isDisabled: boolean;
  onStartRecording: () => void;
  onStopRecording: () => void;
}

export function CentralStartButton({ 
  isRecording, 
  isDisabled, 
  onStartRecording, 
  onStopRecording 
}: CentralStartButtonProps) {
  if (isRecording) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <div className="relative mb-4">
          <div className="w-24 h-24 bg-red-100 rounded-full flex items-center justify-center animate-pulse">
            <div className="w-8 h-8 bg-red-500 rounded-sm"></div>
          </div>
        </div>
        <Button
          onClick={onStopRecording}
          variant="outline"
          size="sm"
          className="text-red-600 border-red-200 hover:bg-red-50"
        >
          Stop Recording
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center py-12">
      <div className="relative mb-6">
        <Button
          onClick={onStartRecording}
          disabled={isDisabled}
          className="w-32 h-32 rounded-full bg-hw-primary hover:bg-hw-primary/90 disabled:bg-hw-accent p-6 shadow-lg hover:shadow-xl transition-all duration-200 hover:scale-105"
        >
          <Image
            src="/hw_buddy_icon.png"
            alt="Start Studying"
            width={80}
            height={80}
            className="rounded-lg"
          />
        </Button>
      </div>
      <h2 className="text-2xl font-bold text-hw-primary mb-2">Ready to Study!</h2>
      <p className="text-hw-accent text-center max-w-md">
        Click the button above to start studying with your AI homework buddy. 
        I'll listen to your questions and help you with your work!
      </p>
    </div>
  );
}