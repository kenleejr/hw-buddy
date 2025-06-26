"use client";

import * as React from "react";
import Image from "next/image";
import { Button } from "./button";
import { ImageModal } from "./image-modal";

interface SeeWhatISeeButtonProps {
  imageUrl: string | null;
  isAnalyzing: boolean;
}

export function SeeWhatISeeButton({ imageUrl, isAnalyzing }: SeeWhatISeeButtonProps) {
  const [isModalOpen, setIsModalOpen] = React.useState(false);

  return (
    <>
      <Button
        onClick={() => setIsModalOpen(true)}
        variant="outline"
        className="flex items-center gap-2 bg-white hover:bg-hw-light border-2 border-hw-primary/20 hover:border-hw-primary/40 transition-all"
      >
        <div className="relative">
          <Image
            src="/hw_buddy_icon.png"
            alt="HW Buddy"
            width={20}
            height={20}
            className="rounded-sm"
          />
          {isAnalyzing && (
            <div className="absolute inset-0 bg-hw-primary/20 rounded-sm animate-pulse"></div>
          )}
        </div>
        <span className="font-medium text-hw-primary">See what I see!</span>
      </Button>

      <ImageModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        imageUrl={imageUrl}
        isAnalyzing={isAnalyzing}
      />
    </>
  );
}