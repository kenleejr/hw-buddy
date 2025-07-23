"use client";

import { useEffect, useRef, useState } from 'react';
import { BackendAudioClient, BackendMessage } from '../utils/backendAudioClient';
import { EventParser, ADKEventData } from '../utils/eventParser';
import { Navigation } from '@/components/ui/navigation';
import { CentralStartButton } from '@/components/ui/central-start-button';
import { ChatPanel } from '@/components/ui/chat-panel';
import { ProcessingStatus } from './ProcessingStatus';
import { MathJaxDisplay } from './MathJaxDisplay';
import VisualizationPanel from './VisualizationPanel';
import { SeeWhatISeeButton } from '@/components/ui/see-what-i-see-button';

// Helper function to normalize backslashes for MathJax (from GeminiLiveSession)
const normalizeMathJaxBackslashes = (content: string): string => {
  if (!content) return content;
  
  // Replace double backslashes with single backslashes for proper MathJax rendering
  return content
    .replace(/\\\\/g, '\\')
    .replace(/\\n/g, '\n')
    .replace(/\\t/g, '\t');
};

interface BackendAudioSessionProps {
  sessionId: string;
  onEndSession: () => void;
}

interface ConversationMessage {
  timestamp: Date;
  type: 'user' | 'assistant';
  content: string;
}

export function BackendAudioSession({ sessionId, onEndSession }: BackendAudioSessionProps) {
  const [isRecording, setIsRecording] = useState(false);
  const [status, setStatus] = useState('Initializing...');
  const [error, setError] = useState('');
  const [conversation, setConversation] = useState<ConversationMessage[]>([]);
  const [audioLevel, setAudioLevel] = useState(0);
  const [lastImageUrl, setLastImageUrl] = useState<string | null>(null);
  const [currentUserMessage, setCurrentUserMessage] = useState('');
  const [currentAssistantMessage, setCurrentAssistantMessage] = useState('');
  const [isAnalyzingImage, setIsAnalyzingImage] = useState(false);
  const [currentMathJax, setCurrentMathJax] = useState('');
  const [connectionStatus, setConnectionStatus] = useState('disconnected');
  const [processingStatus, setProcessingStatus] = useState('');
  const [visualizationConfig, setVisualizationConfig] = useState<any>(null);
  const [showVisualization, setShowVisualization] = useState(false);
  
  const audioClientRef = useRef<BackendAudioClient | null>(null);
  const processingStatusRef = useRef<HTMLDivElement>(null);
  const initializingRef = useRef<boolean>(false);

  // Debug logging for currentMathJax changes (disabled for cleaner logs)
  // useEffect(() => {
  //   console.log('🎵 currentMathJax state changed:', currentMathJax);
  // }, [currentMathJax]);

  // Auto-scroll to ProcessingStatus when MathJax content updates
  useEffect(() => {
    if (currentMathJax && processingStatusRef.current) {
      setTimeout(() => {
        processingStatusRef.current?.scrollIntoView({ 
          behavior: 'smooth', 
          block: 'center',
          inline: 'nearest'
        });
      }, 50);
    }
  }, [currentMathJax]);

  // Auto-scroll to ProcessingStatus when it appears
  useEffect(() => {
    if (processingStatus && processingStatusRef.current) {
      setTimeout(() => {
        processingStatusRef.current?.scrollIntoView({ 
          behavior: 'smooth', 
          block: 'center',
          inline: 'nearest'
        });
      }, 300);
    }
  }, [processingStatus]);

  useEffect(() => {
    initializeBackendAudioClient();
    return () => {
      cleanup();
    };
  }, [sessionId]);

  const cleanup = () => {
    if (audioClientRef.current) {
      audioClientRef.current.disconnect();
      audioClientRef.current = null;
    }
    initializingRef.current = false;
  };

  const initializeBackendAudioClient = async () => {
    try {
      // Prevent multiple initializations
      if (audioClientRef.current || initializingRef.current) {
        console.log('🎵 Audio client already exists or initializing, skipping initialization');
        return;
      }
      
      initializingRef.current = true;
      console.log('🎵 Initializing backend audio client...');
      setStatus('Connecting to backend...');
      
      // Create audio client
      const audioClient = new BackendAudioClient({
        inputSampleRate: 16000,
        outputSampleRate: 24000,
        inputBufferSize: 512,
        outputBufferSize: 1024,
      });

      // Set up event handlers
      audioClient.onMessage = handleBackendMessage;
      audioClient.onAudioLevel = setAudioLevel;
      audioClient.onConnectionChange = (connected) => {
        setConnectionStatus(connected ? 'connected' : 'disconnected');
        if (connected) {
          setStatus('Connected! Ready to record.');
          setError('');
        } else {
          setStatus('Disconnected from backend');
        }
      };
      audioClient.onError = (errorMessage) => {
        console.error('🎵 Audio client error:', errorMessage);
        setError(errorMessage);
        setStatus('Connection error');
      };

      // Connect to backend
      await audioClient.connect(sessionId, 'ws://127.0.0.1:8000');
      
      audioClientRef.current = audioClient;
      initializingRef.current = false;
      
    } catch (err: any) {
      console.error('🎵 Failed to initialize backend audio client:', err);
      setError(`Failed to connect: ${err.message}`);
      setStatus('Failed to connect to backend');
      initializingRef.current = false;
    }
  };

  const handleBackendMessage = (message: BackendMessage) => {
    // Skip logging audio messages to reduce noise
    if (message.type !== 'audio') {
      console.log('🔌 Backend message:', message.type);
    }

    switch (message.type) {
      case 'agent_ready':
        setStatus(message.data?.message || 'Agent ready');
        break;
        
      case 'tool_call':
        console.log('🔌 Tool call:', message.data);
        setIsAnalyzingImage(true);
        setStatus('📸 Taking picture of your homework...');
        setProcessingStatus(message.data?.message || 'Analyzing your homework...');
        
        // Set image URL when a picture is taken (using current session)
        if (message.data?.tool === 'take_picture_and_analyze_tool' || 
            message.data?.message?.includes('picture')) {
          // Check if image is available in the session after a brief delay
          setTimeout(() => {
            setLastImageUrl(`http://localhost:8000/sessions/${sessionId}/image`);
          }, 1000); // Give time for the image to be stored in session
        }
        break;
        
      case 'turn_complete':
        console.log('🔌 Turn complete');
        setStatus('Ready for your next question!');
        setIsAnalyzingImage(false);
        
        // Finalize current assistant message
        if (currentAssistantMessage.trim()) {
          setConversation(prev => [
            ...prev,
            {
              timestamp: new Date(),
              type: 'assistant',
              content: currentAssistantMessage.trim()
            }
          ]);
          setCurrentAssistantMessage('');
        }
        break;
        
      case 'interrupted':
        console.log('🔌 Interrupted');
        setStatus('Go ahead, I\'m listening!');
        setCurrentAssistantMessage('');
        setIsAnalyzingImage(false);
        setProcessingStatus(''); // Clear any processing status
        setCurrentMathJax(''); // Clear current math content to prepare for new response
        break;
        
      case 'error':
        setError(message.data?.message || 'An error occurred');
        setStatus('❌ Error occurred');
        setIsAnalyzingImage(false);
        break;
        
      case 'text':
        // Handle text responses (for transcription/debugging)
        const textContent = message.data?.content || '';
        if (textContent) {
          setCurrentAssistantMessage(prev => prev + textContent);
        }
        break;
        
      case 'image_received':
        setProcessingStatus('Image received, analyzing...');
        // Set image URL when image is received and stored in session
        const imageUrl = `http://localhost:8000/sessions/${sessionId}/image`;
        console.log('🔌 Setting image URL:', imageUrl);
        setLastImageUrl(imageUrl);
        break;
        
      case 'image_analyzed':
        setProcessingStatus('Analysis complete!');
        const analysis = message.data?.analysis;
        
        if (analysis?.mathjax_content) {
          setCurrentMathJax(analysis.mathjax_content);
        }
        
        // Clear processing status after a delay
        setTimeout(() => {
          setProcessingStatus('');
        }, 2000);
        break;
        
      case 'adk_event':
        console.log('🔌 ADK Event:', message.data);
        
        // Use EventParser to handle the event (same as GeminiLiveSession)
        const eventData: ADKEventData = {
          event_id: message.data.event_id || '',
          author: message.data.author || '',
          timestamp: message.data.timestamp || 0,
          is_final: message.data.is_final || false,
          function_call: message.data.function_call,
          function_response: message.data.function_response,
          has_text_content: message.data.has_text_content,
          content: message.data.content
        };
        
        const parseResult = EventParser.parseEvent(eventData);
        
        // Apply the parsing results
        if (parseResult.processingStatus) {
          setProcessingStatus(parseResult.processingStatus);
        }
        
        if (parseResult.shouldUpdateMathJax && parseResult.mathJaxContent) {
          console.log('🔌 Updating MathJax from EventParser:', parseResult.mathJaxContent);
          const normalizedMathJax = normalizeMathJaxBackslashes(parseResult.mathJaxContent);
          console.log('🔌 Setting MathJax content (normalized):', normalizedMathJax);
          setCurrentMathJax(normalizedMathJax);
        }

        // Handle visualization updates
        if (parseResult.shouldShowVisualization && parseResult.visualizationConfig) {
          console.log('🔌 Updating visualization from EventParser:', parseResult.visualizationConfig);
          setVisualizationConfig(parseResult.visualizationConfig);
          setShowVisualization(true);
        }

        // Handle image URL updates
        if (parseResult.shouldUpdateImage && parseResult.imageUrl) {
          console.log('🔌 Updating image URL from EventParser:', parseResult.imageUrl);
          setLastImageUrl(parseResult.imageUrl);
        }
        
        if (parseResult.clearProcessingStatus) {
          // Clear processing status after a delay
          setTimeout(() => {
            setProcessingStatus('');
          }, 2000);
        }
        
        break;
        
      case 'recording_started':
        setStatus('🔴 Recording... Speak now!');
        break;
        
      case 'recording_stopped':
        setStatus('Processing your question...');
        break;
        
      default:
        console.log('🔌 Unhandled message type:', message.type);
    }
  };

  const startRecording = async () => {
    if (!audioClientRef.current || isRecording) return;
    
    try {
      setStatus('Starting recording...');
      await audioClientRef.current.startRecording();
      setIsRecording(true);
      
      // Clear any previous messages for new interaction
      setCurrentUserMessage('');
      setCurrentAssistantMessage('');
      
      // Clear previous content and interrupt audio when starting new recording
      if (currentMathJax || processingStatus) {
        // Immediately interrupt any playing audio
        audioClientRef.current.interruptAudio();
        
        setProcessingStatus('New question detected - interrupting previous response...');
        setTimeout(() => {
          setCurrentMathJax('');
          setProcessingStatus('');
        }, 1000);
      }
      
    } catch (err: any) {
      console.error('🎤 Error starting recording:', err);
      
      let errorMessage = `Failed to start recording: ${err.message}`;
      if (err.name === 'NotAllowedError') {
        errorMessage = 'Microphone permission denied. Please allow microphone access and try again.';
      } else if (err.name === 'NotFoundError') {
        errorMessage = 'No microphone found. Please check your audio devices.';
      }
      
      setError(errorMessage);
      setStatus('Failed to start recording');
    }
  };

  const stopRecording = () => {
    if (!audioClientRef.current || !isRecording) return;
    
    audioClientRef.current.stopRecording();
    setIsRecording(false);
    setAudioLevel(0);
    setStatus('Processing...');
    
    // Add user message if we captured any speech
    if (currentUserMessage.trim()) {
      setConversation(prev => [
        ...prev,
        {
          timestamp: new Date(),
          type: 'user',
          content: currentUserMessage.trim()
        }
      ]);
      setCurrentUserMessage('');
    }
  };

  const handleEndSession = () => {
    cleanup();
    onEndSession();
  };

  return (
    <div className="min-h-screen bg-hw-light">
      {/* Navigation with Status */}
      <Navigation 
        currentPage="hw-buddy"
        sessionId={sessionId}
        status={status}
        error={error}
        audioLevel={audioLevel}
        isRecording={isRecording}
        onEndSession={handleEndSession}
        onStopRecording={stopRecording}
      />
      
      <div className="container mx-auto px-4 py-8">
        {/* Connection Status Indicator */}
        <div className="fixed top-20 right-4 z-50">
          <div className={`px-3 py-1 rounded-full text-xs font-medium ${
            connectionStatus === 'connected' 
              ? 'bg-green-100 text-green-800 border border-green-200' 
              : 'bg-red-100 text-red-800 border border-red-200'
          }`}>
            {connectionStatus === 'connected' ? '🔗 Connected' : '❌ Disconnected'}
          </div>
        </div>

        {/* See What I See Button - Top left corner */}
        {lastImageUrl && (
          <div className="fixed top-20 left-4 z-50">
            <SeeWhatISeeButton 
              imageUrl={lastImageUrl}
              isAnalyzing={isAnalyzingImage}
            />
          </div>
        )}
        
        {/* Central Start Button - only show when not recording and no conversation */}
        {!isRecording && conversation.length === 0 && !currentUserMessage && !currentAssistantMessage && connectionStatus === 'connected' && (
          <CentralStartButton
            isRecording={false}
            isDisabled={!!error || connectionStatus !== 'connected'}
            onStartRecording={startRecording}
            onStopRecording={stopRecording}
          />
        )}
        
        {/* Main Content - Show when there's activity */}
        {(conversation.length > 0 || currentUserMessage || currentAssistantMessage || isRecording || currentMathJax || showVisualization) && (
          <div className="space-y-8">
            {/* Content Container with responsive layout */}
            <div className={`transition-all duration-300 ${showVisualization ? 'pr-[45%]' : ''}`}>
              {/* MathJax Display - Front and Center */}
              <MathJaxDisplay content={currentMathJax} />
              
              {/* Processing Status - Below MathJax */}
              <ProcessingStatus ref={processingStatusRef} status={processingStatus} />
              
            </div>
            
            {/* Chat Panel - Hidden by default, can be toggled if needed */}
            <div className="hidden">
              <ChatPanel
                conversation={conversation}
                currentUserMessage={currentUserMessage}
                currentAssistantMessage={currentAssistantMessage}
                lastImageUrl={lastImageUrl}
                isAnalyzingImage={isAnalyzingImage}
                currentMathJax={currentMathJax}
                processingStatus={processingStatus}
              />
            </div>
          </div>
        )}

        {/* Visualization Panel - Slides in from the right */}
        <VisualizationPanel
          config={visualizationConfig}
          isVisible={showVisualization}
          onClose={() => setShowVisualization(false)}
        />
        
        {/* Error State */}
        {error && (
          <div className="fixed bottom-4 left-4 right-4 max-w-md mx-auto">
            <div className="bg-red-50 border border-red-200 rounded-lg p-4">
              <div className="flex">
                <div className="flex-shrink-0">
                  <div className="w-5 h-5 text-red-400">❌</div>
                </div>
                <div className="ml-3">
                  <h3 className="text-sm font-medium text-red-800">
                    Connection Error
                  </h3>
                  <div className="mt-2 text-sm text-red-700">
                    {error}
                  </div>
                  <div className="mt-4">
                    <button
                      onClick={() => {
                        setError('');
                        initializeBackendAudioClient();
                      }}
                      className="text-sm bg-red-100 text-red-800 px-3 py-1 rounded hover:bg-red-200"
                    >
                      Retry Connection
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
        
        {/* Disconnected State */}
        {!error && connectionStatus === 'disconnected' && (
          <div className="fixed bottom-4 left-4 right-4 max-w-md mx-auto">
            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
              <div className="flex">
                <div className="flex-shrink-0">
                  <div className="w-5 h-5 text-yellow-400">⚠️</div>
                </div>
                <div className="ml-3">
                  <h3 className="text-sm font-medium text-yellow-800">
                    Connecting to Backend...
                  </h3>
                  <div className="mt-2 text-sm text-yellow-700">
                    Please make sure the backend server is running on port 8000
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}