"use client";

import { useEffect, useState } from 'react';

interface ProcessingStatusProps {
  status: string;
}

export function ProcessingStatus({ status }: ProcessingStatusProps) {
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
      }, 150);
    } else if (!status) {
      // Fade out when status is cleared
      setIsVisible(false);
      setTimeout(() => {
        setCurrentStatus('');
      }, 150);
    }
  }, [status, currentStatus]);

  if (!currentStatus) return null;

  return (
    <div className="flex justify-center mt-8">
      <div 
        className={`
          inline-flex items-center px-6 py-3 rounded-full 
          bg-gradient-to-r from-blue-50 to-purple-50 
          border border-blue-200 shadow-sm
          transform transition-all duration-300 ease-in-out
          ${isVisible 
            ? 'opacity-100 scale-100 translate-y-0' 
            : 'opacity-0 scale-95 translate-y-2'
          }
        `}
      >
        <div className="text-sm font-medium text-blue-800 animate-pulse">
          {currentStatus}
        </div>
      </div>
    </div>
  );
}