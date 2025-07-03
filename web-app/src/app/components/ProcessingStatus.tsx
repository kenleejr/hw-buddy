"use client";

import { useEffect, useState, forwardRef } from 'react';

interface ProcessingStatusProps {
  status: string;
}

export const ProcessingStatus = forwardRef<HTMLDivElement, ProcessingStatusProps>(
  ({ status }, ref) => {
    const [isVisible, setIsVisible] = useState(false);
    const [currentStatus, setCurrentStatus] = useState('');

  useEffect(() => {
    if (status && status !== currentStatus) {
      // Fade out current status
      setIsVisible(false);
      
      // After fade out, update status and fade in
      setTimeout(() => {
        setCurrentStatus(status);
        setIsVisible(true);
      }, 200);
    } else if (!status) {
      // Fade out when status is cleared
      setIsVisible(false);
      setTimeout(() => {
        setCurrentStatus('');
      }, 200);
    }
  }, [status, currentStatus]);

  if (!currentStatus) return null;

    return (
      <div ref={ref} className="flex justify-center mt-12">
        <div 
          className={`
            flex items-center justify-center px-12 py-8 rounded-2xl 
            bg-gradient-to-br from-blue-100 to-purple-100 
            border-2 border-blue-300 shadow-lg
            min-w-[400px] min-h-[120px]
            transform transition-all duration-700 ease-in-out
            ${isVisible 
              ? 'opacity-100 scale-100 translate-y-0' 
              : 'opacity-0 scale-90 translate-y-4'
            }
          `}
        >
          <div className="text-2xl font-bold text-blue-900 animate-pulse text-center">
            {currentStatus}
          </div>
        </div>
      </div>
    );
  }
);

ProcessingStatus.displayName = 'ProcessingStatus';