"use client";

import * as React from "react";

interface MathJaxRendererProps {
  content: string;
  className?: string;
}

export function MathJaxRenderer({ content, className = "" }: MathJaxRendererProps) {
  const [isLoaded, setIsLoaded] = React.useState(false);
  const mathRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    console.log('🧮 MathJax Renderer: Starting initialization...');
    console.log('🧮 Window available:', typeof window !== 'undefined');
    console.log('🧮 MathJax already exists:', !!window?.MathJax);
    
    // Load MathJax dynamically (no polyfill needed for modern browsers)
    if (typeof window !== 'undefined' && !window.MathJax) {
      console.log('🧮 Loading MathJax from CDN...');
      
      // Configure MathJax before loading
      window.MathJax = {
        tex: {
          inlineMath: [['$', '$'], ['\\(', '\\)']],
          displayMath: [['$$', '$$'], ['\\[', '\\]']],
          processEscapes: true,
          processEnvironments: true
        },
        options: {
          menuOptions: {
            settings: {
              zoom: 'NoZoom'
            }
          }
        },
        startup: {
          ready: () => {
            console.log('🧮 MathJax startup ready, calling defaultReady...');
            window.MathJax.startup.defaultReady();
            console.log('🧮 MathJax fully initialized, setting loaded state');
            setIsLoaded(true);
          }
        }
      };
      
      const mathJaxScript = document.createElement('script');
      mathJaxScript.id = 'MathJax-script';
      mathJaxScript.src = 'https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js';
      
      mathJaxScript.onload = () => {
        console.log('🧮 MathJax script loaded successfully');
      };
      
      mathJaxScript.onerror = (error) => {
        console.error('🧮 Failed to load MathJax script:', error);
      };
      
      document.head.appendChild(mathJaxScript);
    } else if (window.MathJax) {
      console.log('🧮 MathJax already exists, setting loaded state');
      setIsLoaded(true);
    }
  }, []);

  React.useEffect(() => {
    console.log('🧮 Content effect triggered:', { content, isLoaded, hasRef: !!mathRef.current, hasTypesetPromise: !!window.MathJax?.typesetPromise });
    
    if (isLoaded && mathRef.current && window.MathJax?.typesetPromise) {
      console.log('🧮 Starting MathJax typesetting for content:', content);
      
      window.MathJax.typesetPromise([mathRef.current])
        .then(() => {
          console.log('🧮 MathJax typesetting completed successfully');
        })
        .catch((err: any) => {
          console.error('🧮 MathJax typesetting failed:', err);
        });
    } else {
      console.log('🧮 Skipping typesetting - conditions not met');
    }
  }, [content, isLoaded]);

  if (!content || content.trim() === "") {
    return null;
  }

  return (
    <div className={`mathjax-container bg-white rounded-lg shadow-lg p-6 border border-border ${className}`}>
      <div className="text-center">
        <div className="text-sm font-medium text-hw-accent mb-3">📚 Problem Analysis</div>
        <div className="text-lg leading-relaxed" ref={mathRef}>
          {isLoaded ? content : (
            <div className="animate-pulse">Loading math...</div>
          )}
        </div>
      </div>
    </div>
  );
}

// Add MathJax type declarations
declare global {
  interface Window {
    MathJax: any;
  }
}