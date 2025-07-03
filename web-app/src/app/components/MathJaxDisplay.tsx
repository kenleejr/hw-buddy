"use client";

import { useEffect, useRef } from 'react';

interface MathJaxDisplayProps {
  content: string;
}

export function MathJaxDisplay({ content }: MathJaxDisplayProps) {
  const contentRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (content && contentRef.current) {
      // Process content for better HTML rendering
      const processedContent = content
        // Convert markdown-style bold to HTML
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        // Convert line breaks to HTML breaks for better spacing
        .replace(/\n\n/g, '<br><br>')
        .replace(/\n/g, '<br>');

      // Update the content
      contentRef.current.innerHTML = processedContent;

      // Trigger MathJax to process the new content
      if (typeof window !== 'undefined' && (window as any).MathJax?.typesetPromise) {
        (window as any).MathJax.typesetPromise([contentRef.current]).catch((err: any) => {
          console.error('MathJax typeset failed:', err);
        });
      }
    }
  }, [content]);

  if (!content) {
    return (
      <div className="flex justify-center items-center min-h-[200px]">
        <div className="text-gray-400 text-lg">
          📚 Your problem will appear here...
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-center">
      <div className="max-w-4xl w-full">
        <div 
          ref={contentRef}
          className="
            bg-white rounded-lg shadow-lg border border-gray-200 
            p-8 text-lg leading-relaxed
            transform transition-all duration-300 ease-in-out
            hover:shadow-xl
          "
          style={{ 
            minHeight: '200px',
            lineHeight: '1.8',
            // Better typography for mathematical content
            fontFamily: 'Computer Modern, Times, serif'
          }}
        />
      </div>
    </div>
  );
}