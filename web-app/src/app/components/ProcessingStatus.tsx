"use client";

import { useEffect, useState, forwardRef } from 'react';

interface ProcessingStatusProps {
  status: string;
  shouldAnimate?: boolean;
}

export const ProcessingStatus = forwardRef<HTMLDivElement, ProcessingStatusProps>(
  ({ status, shouldAnimate = true }, ref) => {
    const [isVisible, setIsVisible] = useState(false);
    const [currentStatus, setCurrentStatus] = useState('');

  useEffect(() => {
    if (status && status !== currentStatus) {
      if (shouldAnimate) {
        // Fade out current status
        setIsVisible(false);
        
        // After fade out, update status and fade in
        setTimeout(() => {
          setCurrentStatus(status);
          setIsVisible(true);
        }, 200);
      } else {
        // Just update the text without animation
        setCurrentStatus(status);
        setIsVisible(true);
      }
    } else if (!status) {
      // Fade out when status is cleared
      setIsVisible(false);
      setTimeout(() => {
        setCurrentStatus('');
      }, 200);
    }
  }, [status, currentStatus, shouldAnimate]);

  if (!currentStatus) return null;

    return (
      <div ref={ref}>
        <div 
          className={`
            flex items-center justify-center rounded-2xl 
            bg-gradient-to-br from-blue-100 to-purple-100 
            border-2 border-blue-300 shadow-lg
            px-6 py-4 w-full max-w-sm mx-auto
            ${shouldAnimate 
              ? 'transform transition-all duration-700 ease-in-out' 
              : 'transition-opacity duration-200'
            }
            ${isVisible 
              ? 'opacity-100 scale-100 translate-y-0' 
              : shouldAnimate 
                ? 'opacity-0 scale-90 translate-y-4'
                : 'opacity-0'
            }
          `}
        >
          <div className="font-bold text-blue-900 animate-pulse text-center text-sm">
            {currentStatus}
          </div>
        </div>
      </div>
    );
  }
);

ProcessingStatus.displayName = 'ProcessingStatus';