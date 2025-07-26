"use client";

import { useEffect, useRef, useState } from 'react';

interface MathJaxDisplayProps {
  content: string;
  onActionClick?: (action: string) => void;
}

export function MathJaxDisplay({ content, onActionClick }: MathJaxDisplayProps) {
  const contentRef = useRef<HTMLDivElement>(null);
  const [isVisible, setIsVisible] = useState(false);
  const [hasContent, setHasContent] = useState(false);

  useEffect(() => {
    if (content && contentRef.current) {
      // Fade out first if we already have content
      if (hasContent) {
        setIsVisible(false);
        setTimeout(() => {
          updateContent();
        }, 200);
      } else {
        updateContent();
      }
    } else if (!content && !hasContent) {
      // Only show action cards if we've never had content before
      // If we had content before, keep showing it until new content arrives
      setIsVisible(false);
      setHasContent(false);
    }
  }, [content, hasContent]);

  const updateContent = () => {
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
      setHasContent(true);

      // Trigger MathJax to process the new content
      if (typeof window !== 'undefined' && (window as any).MathJax?.typesetPromise) {
        (window as any).MathJax.typesetPromise([contentRef.current]).then(() => {
          // Show with animation after MathJax processing
          setIsVisible(true);
        }).catch((err: any) => {
          console.error('MathJax typeset failed:', err);
          setIsVisible(true); // Show anyway
        });
      } else {
        setIsVisible(true);
      }
    }
  };

  if (!content && !hasContent) {
    const cards = [
      {
        id: 'hint',
        title: 'Ask me for a hint!'
      },
      {
        id: 'visualization',
        title: 'Ask me for a visualization!'
      },
      {
        id: 'search',
        title: 'Search the internet or my textbook!'
      }
    ];

    return (
      <div className="flex justify-center items-center min-h-[200px] p-4">
        <div className="max-w-4xl w-full">
          <p className="text-center text-lg text-gray-700 mb-6">
            Tell me about the problem you are working on and how I can help
          </p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {cards.map((card) => (
              <div
                key={card.id}
                onClick={() => onActionClick?.(card.id)}
                className="
                  bg-white rounded-2xl shadow-lg 
                  p-6 border border-gray-100
                "
              >
                <h3 className="font-bold text-lg mb-2 leading-tight text-gray-800 text-center">
                  {card.title}
                </h3>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-center">
      <div className="max-w-4xl w-full">
        <div 
          ref={contentRef}
          className={`
            bg-white rounded-3xl shadow-lg border border-gray-200 
            p-8 text-lg leading-relaxed
            transform transition-all duration-500 ease-in-out
            hover:shadow-xl
            ${isVisible 
              ? 'opacity-100 scale-100 translate-y-0' 
              : 'opacity-0 scale-95 translate-y-3'
            }
          `}
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