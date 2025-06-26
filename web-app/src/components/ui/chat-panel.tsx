"use client";

import * as React from "react";
import { Card, CardContent, CardHeader } from "./card";
import { SeeWhatISeeButton } from "./see-what-i-see-button";
import { MathJaxRenderer } from "./mathjax-renderer";

interface ConversationMessage {
  timestamp: Date;
  type: 'user' | 'assistant';
  content: string;
}

interface ChatPanelProps {
  conversation: ConversationMessage[];
  currentUserMessage: string;
  currentAssistantMessage: string;
  lastImageUrl: string | null;
  isAnalyzingImage: boolean;
  currentMathJax: string;
}

export function ChatPanel({ 
  conversation, 
  currentUserMessage, 
  currentAssistantMessage,
  lastImageUrl,
  isAnalyzingImage,
  currentMathJax
}: ChatPanelProps) {
  const conversationEndRef = React.useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when messages update
  React.useEffect(() => {
    if (conversationEndRef.current) {
      conversationEndRef.current.scrollIntoView({ 
        behavior: 'smooth',
        block: 'end'
      });
    }
  }, [conversation, currentUserMessage, currentAssistantMessage]);

  return (
    <div className="w-full max-w-6xl mx-auto">
      {/* Checking Animation */}
      {isAnalyzingImage && (
        <div className="flex items-center justify-center mb-4">
          <div className="bg-white rounded-lg shadow-lg px-6 py-3 flex items-center gap-3 border border-border">
            <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-hw-primary"></div>
            <span className="text-hw-primary font-medium">Checking your work...</span>
          </div>
        </div>
      )}
      
      {/* MathJax Renderer */}
      {currentMathJax && (
        <div className="mb-4">
          <MathJaxRenderer content={currentMathJax} />
        </div>
      )}
      
      <Card className="shadow-lg">
        <CardHeader className="pb-4">
          <div className="flex items-center justify-between">
            <SeeWhatISeeButton 
              imageUrl={lastImageUrl}
              isAnalyzing={isAnalyzingImage}
            />
          </div>
        </CardHeader>
        
        <CardContent>
          <div className="h-96 overflow-y-auto bg-hw-light/30 p-6 rounded-lg border border-border">
            {conversation.length === 0 && !currentUserMessage && !currentAssistantMessage ? (
              <div className="text-center text-hw-accent py-12">
                <div className="text-6xl mb-4">🎓</div>
                <div className="text-lg font-medium mb-2">Welcome to your study session!</div>
                <div className="text-sm">Start recording to begin your conversation with your AI homework buddy!</div>
              </div>
            ) : (
              <div className="space-y-4">
                {conversation.map((message, index) => (
                  <div key={index} className="message-bubble">
                    <div className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}>
                      <div className={`max-w-[80%] p-4 rounded-2xl ${
                        message.type === 'user' 
                          ? 'bg-hw-primary text-white ml-12' 
                          : 'bg-white text-foreground mr-12 shadow-sm border border-border'
                      }`}>
                        <div className={`text-xs font-medium mb-2 opacity-75 ${
                          message.type === 'user' ? 'text-white/80' : 'text-hw-accent'
                        }`}>
                          {message.type === 'user' ? '👤 You' : '🤖 Assistant'}
                        </div>
                        <div className="text-base leading-relaxed font-['Comic_Neue',_'Quicksand',_'Nunito',_sans-serif]">
                          {message.content}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
                
                {/* Live streaming user message */}
                {currentUserMessage && (
                  <div className="flex justify-end">
                    <div className="max-w-[80%] p-4 rounded-2xl bg-hw-primary/80 text-white ml-12">
                      <div className="text-xs font-medium mb-2 opacity-75 text-white/80">
                        👤 You
                      </div>
                      <div className="text-base leading-relaxed font-['Comic_Neue',_'Quicksand',_'Nunito',_sans-serif]">
                        {currentUserMessage}
                        <span className="animate-pulse ml-1">|</span>
                      </div>
                    </div>
                  </div>
                )}
                
                {/* Live streaming assistant message */}
                {currentAssistantMessage && (
                  <div className="flex justify-start">
                    <div className="max-w-[80%] p-4 rounded-2xl bg-white text-foreground mr-12 shadow-sm border border-border">
                      <div className="text-xs font-medium mb-2 opacity-75 text-hw-accent">
                        🤖 Assistant
                      </div>
                      <div className="text-base leading-relaxed font-['Comic_Neue',_'Quicksand',_'Nunito',_sans-serif]">
                        {currentAssistantMessage}
                        <span className="animate-pulse ml-1">|</span>
                      </div>
                    </div>
                  </div>
                )}
                
                <div ref={conversationEndRef} className="h-1" />
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}