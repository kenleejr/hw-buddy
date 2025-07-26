"use client";

import * as React from "react";
import Image from "next/image";
import { ImageModal } from "./image-modal";

interface SeeWhatISeeButtonProps {
  imageUrl: string | null;
  isAnalyzing: boolean;
}

export function SeeWhatISeeButton({ imageUrl, isAnalyzing }: SeeWhatISeeButtonProps) {
  const [isModalOpen, setIsModalOpen] = React.useState(false);

  return (
    <>
      <div
        onClick={() => setIsModalOpen(true)}
        className="flex items-center justify-center rounded-2xl bg-gradient-to-br from-green-100 to-blue-100 border-2 border-green-300 shadow-lg px-6 py-4 w-full max-w-sm mx-auto cursor-pointer hover:shadow-xl transition-all duration-300 hover:scale-105"
      >
        <div className="flex items-center gap-3">
          <div className="relative">
            <Image
              src="/hw_buddy_icon.png"
              alt="HW Buddy"
              width={24}
              height={24}
              className="rounded-sm"
            />
            {isAnalyzing && (
              <div className="absolute inset-0 bg-green-400/30 rounded-sm animate-pulse"></div>
            )}
          </div>
          <span className="font-bold text-green-900 text-sm">See what I see!</span>
        </div>
      </div>

      <ImageModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        imageUrl={imageUrl}
        isAnalyzing={isAnalyzing}
      />
    </>
  );
}