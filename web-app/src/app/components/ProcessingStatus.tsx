"use client";

import { useEffect, useState, forwardRef } from 'react';

interface ProcessingStatusProps {
  status: string;
  position?: 'center' | 'top-left';
  shouldAnimate?: boolean;
}

export const ProcessingStatus = forwardRef<HTMLDivElement, ProcessingStatusProps>(
  ({ status, position = 'center', shouldAnimate = true }, ref) => {
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
      <div 
        ref={ref} 
        className={`
          ${position === 'center' 
            ? 'flex justify-center mt-12' 
            : 'fixed top-40 left-4 z-40'
          }
        `}
      >
        <div 
          className={`
            flex items-center justify-center rounded-2xl 
            bg-gradient-to-br from-blue-100 to-purple-100 
            border-2 border-blue-300 shadow-lg
            ${position === 'center' 
              ? 'px-12 py-8 min-w-[400px] min-h-[120px]' 
              : 'px-4 py-3 min-w-[200px] max-w-[300px]'
            }
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
          <div className={`
            font-bold text-blue-900 animate-pulse text-center
            ${position === 'center' ? 'text-2xl' : 'text-sm'}
          `}>
            {currentStatus}
          </div>
        </div>
      </div>
    );
  }
);

ProcessingStatus.displayName = 'ProcessingStatus';