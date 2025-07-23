"use client";

import * as React from "react";
import { Card, CardContent } from "./card";

interface ImageModalProps {
  isOpen: boolean;
  onClose: () => void;
  imageUrl: string | null;
  isAnalyzing: boolean;
}

export function ImageModal({ isOpen, onClose, imageUrl, isAnalyzing }: ImageModalProps) {
  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop */}
      <div 
        className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4"
        onClick={onClose}
      >
        {/* Modal Content */}
        <Card 
          className="max-w-4xl max-h-[90vh] w-full overflow-hidden"
          onClick={(e) => e.stopPropagation()}
        >
          <CardContent className="p-0 relative">
            {/* Close Button */}
            <button
              onClick={onClose}
              className="absolute top-4 right-4 z-10 bg-white rounded-full p-2 shadow-lg hover:bg-gray-100 transition-colors"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>

            {imageUrl ? (
              <div className="relative">
                <img 
                  src={imageUrl} 
                  alt="Your homework"
                  className="w-full h-auto max-h-[80vh] object-contain"
                  onError={(e) => {
                    console.error('Failed to load image:', imageUrl);
                    e.currentTarget.style.display = 'none';
                  }}
                  onLoad={() => {
                    console.log('Image loaded successfully:', imageUrl);
                  }}
                />
                
                {/* Analysis Overlay */}
                {isAnalyzing && (
                  <div className="absolute inset-0 bg-black bg-opacity-30 flex items-center justify-center">
                    <div className="text-center text-white">
                      <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-white mx-auto mb-4"></div>
                      <div className="text-lg font-medium">Checking your work...</div>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="flex items-center justify-center h-96 bg-hw-light">
                <div className="text-center text-hw-accent">
                  <div className="text-6xl mb-4">📷</div>
                  <div className="text-xl font-medium mb-2">No image yet</div>
                  <div className="text-base">Tell me to take a picture of your work</div>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </>
  );
}