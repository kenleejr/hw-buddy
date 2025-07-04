"use client";

import { useEffect, useRef, useState } from 'react';
import { createBlob, decode, decodeAudioData } from '../utils/audio';
import { Navigation } from '@/components/ui/navigation';
import { CentralStartButton } from '@/components/ui/central-start-button';
import { ChatPanel } from '@/components/ui/chat-panel';

interface WebSocketGeminiSessionProps {
  sessionId: string;
  onEndSession: () => void;
}

interface ConversationMessage {
  timestamp: Date;
  type: 'user' | 'assistant';
  content: string;
}

export function WebSocketGeminiSession({ sessionId, onEndSession }: WebSocketGeminiSessionProps) {
  const [isRecording, setIsRecording] = useState(false);
  const [status, setStatus] = useState('Initializing...');
  const [error, setError] = useState('');
  const [conversation, setConversation] = useState<ConversationMessage[]>([]);
  const [audioLevel, setAudioLevel] = useState(0);
  const [lastImageUrl, setLastImageUrl] = useState<string | null>(null);
  const [currentUserMessage, setCurrentUserMessage] = useState('');
  const [currentAssistantMessage, setCurrentAssistantMessage] = useState('');
  const [isAnalyzingImage, setIsAnalyzingImage] = useState(false);
  const [currentMathJax] = useState('');

  // WebSocket and audio refs
  const wsRef = useRef<WebSocket | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const inputAudioContextRef = useRef<AudioContext | null>(null);
  const outputAudioContextRef = useRef<AudioContext | null>(null);
  const inputGainRef = useRef<GainNode | null>(null);
  const outputGainRef = useRef<GainNode | null>(null);
  const workletNodeRef = useRef<AudioWorkletNode | null>(null);
  const conversationEndRef = useRef<HTMLDivElement>(null);
  const sourcesRef = useRef<Set<AudioBufferSourceNode>>(new Set());
  const nextStartTimeRef = useRef<number>(0);

  useEffect(() => {
    initializeSession();
    return () => {
      cleanup();
    };
  }, []);

  useEffect(() => {
    conversationEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [conversation]);

  const cleanup = () => {
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach(track => track.stop());
    }
    if (workletNodeRef.current) {
      workletNodeRef.current.disconnect();
    }
    if (inputGainRef.current) {
      inputGainRef.current.disconnect();
    }
    if (outputGainRef.current) {
      outputGainRef.current.disconnect();
    }
    if (inputAudioContextRef.current) {
      inputAudioContextRef.current.close();
    }
    if (outputAudioContextRef.current) {
      outputAudioContextRef.current.close();
    }
    if (wsRef.current) {
      wsRef.current.close();
    }
  };

  const initializeSession = async () => {
    try {
      console.log('🎵 Initializing WebSocket session...');
      setStatus('Initializing audio...');
      
      // Initialize audio contexts
      inputAudioContextRef.current = new (window.AudioContext || (window as any).webkitAudioContext)({ sampleRate: 16000 });
      outputAudioContextRef.current = new (window.AudioContext || (window as any).webkitAudioContext)({ sampleRate: 24000 });
      
      // Load audio worklet processor
      try {
        await inputAudioContextRef.current.audioWorklet.addModule('/audio-capture-processor.js');
      } catch (error) {
        console.error('🎵 Failed to load audio worklet:', error);
        throw error;
      }
      
      // Create gain nodes
      inputGainRef.current = inputAudioContextRef.current.createGain();
      outputGainRef.current = outputAudioContextRef.current.createGain();
      
      // Connect output gain to destination
      outputGainRef.current.connect(outputAudioContextRef.current.destination);
      
      nextStartTimeRef.current = outputAudioContextRef.current.currentTime;
      
      setStatus('Connecting to WebSocket server...');
      
      // Connect to WebSocket server
      const wsUrl = process.env.NEXT_PUBLIC_WEBSOCKET_URL || 'ws://localhost:8081';
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;
      
      ws.onopen = () => {
        console.log('🎵 WebSocket connected');
        // Join session as web client
        ws.send(JSON.stringify({
          type: 'join_session',
          session_id: sessionId,
          client_type: 'web'
        }));
      };
      
      ws.onmessage = async (event) => {
        try {
          const message = JSON.parse(event.data);
          await handleServerMessage(message);
        } catch (error) {
          console.error('🎵 Error parsing WebSocket message:', error);
        }
      };
      
      ws.onerror = (error) => {
        console.error('🎵 WebSocket error:', error);
        setError('Connection error occurred');
        setStatus('Connection failed');
      };
      
      ws.onclose = (event) => {
        console.log('🎵 WebSocket closed:', event.code, event.reason);
        setStatus(`Connection closed: ${event.reason || 'Unknown reason'}`);
      };
      
    } catch (err: any) {
      console.error('🎵 Failed to initialize session:', err);
      setError(`Failed to initialize: ${err.message}`);
      setStatus('Failed to connect');
    }
  };

  const handleServerMessage = async (message: any) => {
    console.log('🎵 Received message:', message.type);
    
    switch (message.type) {
      case 'ready':
        setStatus('Connected! Ready to record.');
        setError('');
        break;
        
      case 'session_joined':
        console.log('🎵 Joined session:', message.session_id);
        setStatus('Connected! Ready to record.');
        break;
        
      case 'audio':
        // Handle audio response from Gemini
        if (outputAudioContextRef.current && message.data) {
          await playAudioResponse(message.data);
        }
        break;
        
      case 'text':
        // Handle text response from Gemini
        setCurrentAssistantMessage(prev => prev + message.data);
        break;
        
      case 'turn_complete':
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
        
      case 'function_call':
        console.log('🎵 Function call:', message.data.name);
        if (message.data.name === 'capture_image') {
          setIsAnalyzingImage(true);
        }
        break;
        
      case 'function_response':
        console.log('🎵 Function response:', message.data);
        if (message.data.success && message.data.image_url) {
          setLastImageUrl(message.data.image_url);
        }
        setIsAnalyzingImage(false);
        break;
        
      case 'image_uploaded_notification':
        console.log('🎵 Image uploaded via HTTP:', message.message);
        // Could show a brief notification that image was received
        break;
        
      case 'interrupted':
        // Handle interruption
        for (const source of sourcesRef.current.values()) {
          source.stop();
          sourcesRef.current.delete(source);
        }
        nextStartTimeRef.current = 0;
        break;
        
      case 'error':
        console.error('🎵 Server error:', message.data);
        setError(message.data.message || 'Server error occurred');
        break;
        
      default:
        console.log('🎵 Unknown message type:', message.type);
    }
  };

  const playAudioResponse = async (audioData: string) => {
    if (!outputAudioContextRef.current) return;
    
    try {
      nextStartTimeRef.current = Math.max(
        nextStartTimeRef.current,
        outputAudioContextRef.current.currentTime,
      );

      const decodedData = decode(audioData);
      
      const audioBuffer = await decodeAudioData(
        decodedData,
        outputAudioContextRef.current,
        24000,
        1,
      );
      
      const source = outputAudioContextRef.current.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(outputGainRef.current!);
      
      source.addEventListener('ended', () => {
        sourcesRef.current.delete(source);
      });
      
      // Resume context if suspended
      if (outputAudioContextRef.current.state === 'suspended') {
        await outputAudioContextRef.current.resume();
      }
      
      source.start(nextStartTimeRef.current);
      nextStartTimeRef.current = nextStartTimeRef.current + audioBuffer.duration;
      sourcesRef.current.add(source);
      
    } catch (error) {
      console.error('🎵 Error processing audio:', error);
    }
  };

  const startRecording = async () => {
    if (!wsRef.current || isRecording || !inputAudioContextRef.current) return;
    
    try {
      setStatus('Requesting microphone access...');

      console.log('🎤 Checking for available audio devices...');
      const devices = await navigator.mediaDevices.enumerateDevices();
      const audioInputDevices = devices.filter(device => device.kind === 'audioinput');
      console.log('Available Audio Input Devices:', audioInputDevices);
      if (audioInputDevices.length === 0) {
        setError('No audio input devices found.');
        return;
      }
      
      await inputAudioContextRef.current.resume();
      await outputAudioContextRef.current?.resume();
      
      console.log('🎵 Audio contexts resumed - Input:', inputAudioContextRef.current.state, 'Output:', outputAudioContextRef.current?.state);
      
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
      mediaStreamRef.current = stream;
      
      console.log('🎵 Media stream created:', stream);
      
      const source = inputAudioContextRef.current.createMediaStreamSource(stream);
      source.connect(inputGainRef.current!);
      
      // Create AudioWorkletNode
      console.log('🎵 Creating AudioWorkletNode...');
      const workletNode = new AudioWorkletNode(inputAudioContextRef.current, 'audio-capture-processor');
      workletNodeRef.current = workletNode;
      
      console.log('🎵 Connecting audio chain: InputGain → WorkletNode → Destination');
      inputGainRef.current!.connect(workletNode);
      workletNode.connect(inputAudioContextRef.current.destination);
      
      console.log('🎵 Audio chain connected successfully');
      
      setIsRecording(true);
      setStatus('🔴 Recording... Speak now!');
      
      // Handle messages from the audio worklet
      workletNode.port.onmessage = (event) => {
        if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
          return;
        }
        
        const { type, audioData, level, count } = event.data;
        
        if (type === 'audioData') {
          // Update audio level for UI
          setAudioLevel(level * 100);
          
          try {
            // Send audio data to WebSocket server
            const base64 = btoa(String.fromCharCode(...audioData));
            
            wsRef.current?.send(JSON.stringify({
              type: 'audio',
              data: base64
            }));
            
            // Only log occasionally when there's actual audio
            if (count % 500 === 0 && level > 0.01) {
              console.log('🎵 Audio level:', level.toFixed(4), 'sending to server');
            }
          } catch (error) {
            console.error('🎵 Error sending audio to server:', error);
          }
        }
      };
      
      console.log('🎵 Message handler set up successfully');
      
    } catch (err: any) {
      console.error('🎵 Error starting recording:', err);
      
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
    if (!isRecording) return;
    
    setIsRecording(false);
    setAudioLevel(0);
    setStatus('Processing...');
    
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach(track => track.stop());
      mediaStreamRef.current = null;
    }
    
    if (workletNodeRef.current && inputAudioContextRef.current) {
      workletNodeRef.current.disconnect();
      workletNodeRef.current = null;
    }
    
    // Send end signal to server
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'end'
      }));
    }
    
    // Add user message if we have transcript content
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
    
    setTimeout(() => {
      setStatus('Ready for next interaction');
    }, 1000);
  };

  return (
    <div className="min-h-screen bg-hw-light">
      {/* Navigation with Status Modal */}
      <Navigation 
        currentPage="hw-buddy"
        sessionId={sessionId}
        status={status}
        error={error}
        audioLevel={audioLevel}
        isRecording={isRecording}
        onEndSession={onEndSession}
        onStopRecording={stopRecording}
      />
      
      <div className="container mx-auto px-4 py-8">
        {/* Central Start Button - only show when not recording and no conversation */}
        {!isRecording && conversation.length === 0 && !currentUserMessage && !currentAssistantMessage && (
          <CentralStartButton
            isRecording={false}
            isDisabled={!!error}
            onStartRecording={startRecording}
            onStopRecording={stopRecording}
          />
        )}
        
        {/* Chat Panel - Full Width */}
        {(conversation.length > 0 || currentUserMessage || currentAssistantMessage || isRecording) && (
          <ChatPanel
            conversation={conversation}
            currentUserMessage={currentUserMessage}
            currentAssistantMessage={currentAssistantMessage}
            lastImageUrl={lastImageUrl}
            isAnalyzingImage={isAnalyzingImage}
            currentMathJax={currentMathJax}
          />
        )}
      </div>
    </div>
  );
}