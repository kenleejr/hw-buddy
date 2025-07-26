'use client';

import React, { useEffect, useRef, useState } from 'react';
import { Maximize2, Minimize2, ChevronLeft, ChevronRight } from 'lucide-react';

interface VisualizationConfig {
  visualization_type: string;
  html_content?: string;
  chart_config?: any; // Legacy support
  help_text: string;
}

interface VisualizationPanelProps {
  config?: VisualizationConfig;
  isVisible: boolean;
}

export default function VisualizationPanel({ config, isVisible }: VisualizationPanelProps) {
  const contentRef = useRef<HTMLDivElement>(null);
  const [isExpanded, setIsExpanded] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);
  const [isAnimating, setIsAnimating] = useState(false);

  useEffect(() => {
    if (isVisible) {
      setIsAnimating(true);
      setIsMinimized(false); // Reset minimized state when opening
      // Allow animation to complete
      const timer = setTimeout(() => setIsAnimating(false), 300);
      return () => clearTimeout(timer);
    }
  }, [isVisible]);

  // Inject HTML content if available
  useEffect(() => {
    if (config?.html_content && contentRef.current && isVisible && !isMinimized) {
      // Clear existing content first
      contentRef.current.innerHTML = '';
      
      // Set the HTML content
      contentRef.current.innerHTML = config.html_content;
      
      // Execute any script tags in the injected HTML with isolation
      const scripts = contentRef.current.querySelectorAll('script');
      scripts.forEach((script, index) => {
        if (script.src) {
          // External script - just load it
          const newScript = document.createElement('script');
          newScript.src = script.src;
          Array.from(script.attributes).forEach(attr => {
            if (attr.name !== 'src') {
              newScript.setAttribute(attr.name, attr.value);
            }
          });
          script.remove();
          contentRef.current?.appendChild(newScript);
        } else {
          // Inline script - wrap in an IIFE to avoid variable conflicts
          const scriptContent = script.textContent || '';
          const wrappedScript = `
            (function() {
              ${scriptContent}
            })();
          `;
          
          try {
            // Use Function constructor to execute in isolated scope
            const executeScript = new Function(wrappedScript);
            executeScript();
          } catch (error) {
            console.error('Error executing visualization script:', error);
          }
          
          script.remove();
        }
      });
    }
  }, [config?.html_content, isVisible, isMinimized]);

  if (!config) {
    return null;
  }


  const handleToggleExpand = () => {
    setIsExpanded(!isExpanded);
  };

  const handleMinimize = () => {
    setIsMinimized(true);
  };

  const handleMaximize = () => {
    setIsMinimized(false);
  };

  const getVisualizationTitle = () => {
    // Use visualization_type directly or provide generic title
    return config.visualization_type || 'Interactive Visualization';
  };

  const getVisualizationIcon = () => {
    // Generic visualization icon
    return '📊';
  };

  return (
    <>
      {/* Minimized Tab - Shows when minimized */}
      {isMinimized && (
        <div 
          className="fixed right-0 top-20 bg-white shadow-lg border border-gray-200 rounded-l-lg z-30 cursor-pointer hover:bg-gray-50 transition-colors"
          onClick={handleMaximize}
        >
          <div className="flex items-center p-3 space-x-2">
            <span className="text-lg">{getVisualizationIcon()}</span>
            <span className="text-sm font-medium text-gray-700">Visualization</span>
            <ChevronLeft className="h-4 w-4 text-gray-600" />
          </div>
        </div>
      )}

      {/* Full Panel - Shows when visible and not minimized */}
      {isVisible && !isMinimized && (
        <div 
          className={`fixed right-0 top-16 h-[calc(100vh-4rem)] bg-white shadow-2xl border-l border-gray-200 transition-all duration-300 ease-in-out z-30 ${
            isAnimating ? 'animate-pulse' : ''
          } ${
            isExpanded ? 'w-[70%] min-w-[900px]' : 'w-[45%] min-w-[600px]'
          }`}
        >
          {/* Header */}
          <div className="flex items-center justify-between p-4 bg-gradient-to-r from-blue-50 to-purple-50 border-b border-gray-200">
            <div className="flex items-center space-x-3">
              <span className="text-2xl">{getVisualizationIcon()}</span>
              <div>
                <h2 className="text-lg font-semibold text-gray-800">
                  {getVisualizationTitle()}
                </h2>
                <p className="text-sm text-gray-600">Interactive Visualization</p>
              </div>
            </div>
            
            <div className="flex items-center space-x-2">
              <button
                onClick={handleMinimize}
                className="p-2 hover:bg-white hover:bg-opacity-60 rounded-lg transition-colors"
                title="Minimize to tab"
              >
                <ChevronRight className="h-5 w-5 text-gray-600" />
              </button>
              
              <button
                onClick={handleToggleExpand}
                className="p-2 hover:bg-white hover:bg-opacity-60 rounded-lg transition-colors"
                title={isExpanded ? 'Shrink' : 'Expand'}
              >
                {isExpanded ? (
                  <Minimize2 className="h-5 w-5 text-gray-600" />
                ) : (
                  <Maximize2 className="h-5 w-5 text-gray-600" />
                )}
              </button>
            </div>
          </div>

          {/* Content */}
          <div className="flex flex-col h-[calc(100%-4rem)]">
            {/* Visualization Container */}
            <div className="flex-1 p-6 overflow-auto">
              <div className="h-full w-full">
                {config.html_content ? (
                  <div 
                    ref={contentRef} 
                    className="h-full w-full"
                    style={{ minHeight: '400px' }}
                  />
                ) : config.chart_config ? (
                  // Legacy Chart.js support
                  <div>Legacy Chart.js visualization (deprecated)</div>
                ) : (
                  <div className="flex items-center justify-center h-full text-gray-500">
                    No visualization content available
                  </div>
                )}
              </div>
            </div>

            {/* Explanation */}
            <div className="p-6 bg-gray-50 border-t border-gray-200">
              <h3 className="text-sm font-medium text-gray-700 mb-2">
                How this helps:
              </h3>
              <p className="text-sm text-gray-600 leading-relaxed">
                {config.help_text}
              </p>
            </div>
          </div>
        </div>
      )}
    </>
  );
}