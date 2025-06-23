"use client";

import { useEffect, useRef, useState } from 'react';
import { GoogleGenAI, LiveServerMessage, Session, Modality } from '@google/genai';
import { createBlob, decode, decodeAudioData } from '../utils/audio';

interface GeminiLiveSessionProps {
  sessionId: string;
  onEndSession: () => void;
}

interface ConversationMessage {
  timestamp: Date;
  type: 'user' | 'assistant';
  content: string;
}

export function GeminiLiveSession({ sessionId, onEndSession }: GeminiLiveSessionProps) {
  const [isRecording, setIsRecording] = useState(false);
  const [status, setStatus] = useState('Initializing...');
  const [error, setError] = useState('');
  const [conversation, setConversation] = useState<ConversationMessage[]>([]);
  const [currentTranscript, setCurrentTranscript] = useState('');
  
  const sessionRef = useRef<Session | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const inputAudioContextRef = useRef<AudioContext | null>(null);
  const outputAudioContextRef = useRef<AudioContext | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
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
    if (processorRef.current) {
      processorRef.current.disconnect();
    }
    if (inputAudioContextRef.current) {
      inputAudioContextRef.current.close();
    }
    if (outputAudioContextRef.current) {
      outputAudioContextRef.current.close();
    }
    if (sessionRef.current) {
      sessionRef.current.close();
    }
  };

  const initializeSession = async () => {
    try {
      console.log('🎵 Initializing session...');
      setStatus('Initializing audio...');
      
      // Initialize audio contexts
      console.log('🎵 Creating audio contexts...');
      inputAudioContextRef.current = new (window.AudioContext || (window as any).webkitAudioContext)({ sampleRate: 16000 });
      outputAudioContextRef.current = new (window.AudioContext || (window as any).webkitAudioContext)({ sampleRate: 24000 });
      nextStartTimeRef.current = outputAudioContextRef.current.currentTime;
      
      console.log('🎵 Input audio context:', inputAudioContextRef.current);
      console.log('🎵 Output audio context:', outputAudioContextRef.current);
      console.log('🎵 Next start time:', nextStartTimeRef.current);
      
      setStatus('Connecting to Gemini Live API...');
      
      const client = new GoogleGenAI({ 
         apiKey: ""
      });
      
      console.log('🎵 Connecting to Gemini Live API...');
      const session = await client.live.connect({
        model: 'gemini-2.5-flash-preview-native-audio-dialog',
        callbacks: {
          onopen: () => {
            console.log('🎵 Session opened successfully!');
            setStatus('Connected! Ready to record.');
            setError('');
          },
          onmessage: async (message: LiveServerMessage) => {
            console.log('🎵 Received message:', message);
            await handleServerMessage(message);
          },
          onerror: (e: ErrorEvent) => {
            console.error('🎵 Session error:', e);
            setError(`Connection error: ${e.message}`);
            setStatus('Error occurred');
          },
          onclose: (e: CloseEvent) => {
            console.log('🎵 Session closed:', e);
            setStatus(`Connection closed: ${e.reason}`);
          },
        },
        config: {
          responseModalities: [Modality.AUDIO],
          speechConfig: {
            voiceConfig: { prebuiltVoiceConfig: { voiceName: 'Orus' } },
          },
        },
      });
      
      console.log('🎵 Session created:', session);
      sessionRef.current = session;
      
    } catch (err: any) {
      console.error('🎵 Failed to initialize session:', err);
      setError(`Failed to initialize: ${err.message}`);
      setStatus('Failed to connect');
    }
  };

  const handleServerMessage = async (message: LiveServerMessage) => {
    console.log('🎵 Handling server message:', message);
    
    // Handle audio response
    const audio = message.serverContent?.modelTurn?.parts?.[0]?.inlineData;
    console.log('🎵 Audio data found:', !!audio);
    
    if (audio && outputAudioContextRef.current) {
      console.log('🎵 Processing audio response...');
      console.log('🎵 Audio data length:', audio.data?.length);
      console.log('🎵 Audio MIME type:', audio.mimeType);
      
      nextStartTimeRef.current = Math.max(
        nextStartTimeRef.current,
        outputAudioContextRef.current.currentTime,
      );
      console.log('🎵 Scheduled start time:', nextStartTimeRef.current);

      try {
        const decodedData = decode(audio.data);
        console.log('🎵 Decoded data length:', decodedData.length);
        
        const audioBuffer = await decodeAudioData(
          decodedData,
          outputAudioContextRef.current,
          24000,
          1,
        );
        console.log('🎵 Audio buffer created:', audioBuffer);
        console.log('🎵 Audio buffer duration:', audioBuffer.duration);
        
        const source = outputAudioContextRef.current.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(outputAudioContextRef.current.destination);
        
        source.addEventListener('ended', () => {
          console.log('🎵 Audio playback ended');
          sourcesRef.current.delete(source);
        });

        console.log('🎵 Starting audio playback at:', nextStartTimeRef.current);
        source.start(nextStartTimeRef.current);
        nextStartTimeRef.current = nextStartTimeRef.current + audioBuffer.duration;
        sourcesRef.current.add(source);
        
        // Add to conversation for display
        setConversation(prev => [
          ...prev,
          {
            timestamp: new Date(),
            type: 'assistant',
            content: 'Audio response'
          }
        ]);
      } catch (error) {
        console.error('🎵 Error processing audio:', error);
      }
    }

    // Handle interruption
    const interrupted = message.serverContent?.interrupted;
    if (interrupted) {
      console.log('🎵 Handling interruption...');
      for (const source of sourcesRef.current.values()) {
        source.stop();
        sourcesRef.current.delete(source);
      }
      nextStartTimeRef.current = 0;
    }
    
    if (message.serverContent?.turnComplete) {
      console.log('🎵 Turn completed');
      setCurrentTranscript('');
    }
  };

  const startRecording = async () => {
    if (!sessionRef.current || isRecording || !inputAudioContextRef.current) return;
    
    try {
      setStatus('Requesting microphone access...');
      
      await inputAudioContextRef.current.resume();
      
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
      mediaStreamRef.current = stream;
      
      const source = inputAudioContextRef.current.createMediaStreamSource(stream);
      const processor = inputAudioContextRef.current.createScriptProcessor(256, 1, 1);
      processorRef.current = processor;
      
      processor.onaudioprocess = (audioProcessingEvent) => {
        if (!isRecording || !sessionRef.current) return;
        
        const inputBuffer = audioProcessingEvent.inputBuffer;
        const pcmData = inputBuffer.getChannelData(0);
        
        const blob = createBlob(pcmData);
        sessionRef.current.sendRealtimeInput({ media: blob });
      };
      
      source.connect(processor);
      processor.connect(inputAudioContextRef.current.destination);
      
      setIsRecording(true);
      setStatus('🔴 Recording... Speak now!');
      setCurrentTranscript('Listening...');
      
    } catch (err: any) {
      setError(`Failed to start recording: ${err.message}`);
      setStatus('Failed to start recording');
    }
  };

  const stopRecording = () => {
    if (!isRecording) return;
    
    setIsRecording(false);
    setStatus('Processing...');
    
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach(track => track.stop());
      mediaStreamRef.current = null;
    }
    
    if (processorRef.current && inputAudioContextRef.current) {
      processorRef.current.disconnect();
      processorRef.current = null;
    }
    
    setConversation(prev => [
      ...prev,
      {
        timestamp: new Date(),
        type: 'user',
        content: 'Audio message sent'
      }
    ]);
    
    setTimeout(() => {
      setStatus('Ready for next interaction');
    }, 1000);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-50 to-pink-100 p-4">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
          <div className="flex justify-between items-center mb-4">
            <h1 className="text-2xl font-bold text-gray-800">
              Homework Buddy - Session {sessionId}
            </h1>
            <button
              onClick={onEndSession}
              className="bg-red-500 hover:bg-red-600 text-white px-4 py-2 rounded-md transition duration-200"
            >
              End Session
            </button>
          </div>
          
          {/* Status */}
          <div className="flex justify-between items-center">
            <div className="text-sm text-gray-600">
              Status: <span className={error ? 'text-red-600' : 'text-green-600'}>
                {error || status}
              </span>
            </div>
            
            {/* Controls */}
            <div className="flex gap-2">
              {isRecording ? (
                <button
                  onClick={stopRecording}
                  className="bg-red-500 hover:bg-red-600 text-white px-4 py-2 rounded-md transition duration-200"
                >
                  ⏹️ Stop Recording
                </button>
              ) : (
                <button
                  onClick={startRecording}
                  disabled={!!error}
                  className="bg-blue-500 hover:bg-blue-600 disabled:bg-gray-400 text-white px-4 py-2 rounded-md transition duration-200"
                >
                  🎤 Start Recording
                </button>
              )}
            </div>
          </div>
        </div>
        
        {/* Conversation */}
        <div className="bg-white rounded-lg shadow-lg p-6">
          <h2 className="text-xl font-semibold text-gray-800 mb-4">Conversation</h2>
          
          <div className="space-y-4 max-h-96 overflow-y-auto">
            {conversation.length === 0 ? (
              <div className="text-center text-gray-500 py-8">
                Start recording to begin your conversation with Homework Buddy!
              </div>
            ) : (
              conversation.map((message, index) => (
                <div
                  key={index}
                  className={`flex ${
                    message.type === 'user' ? 'justify-end' : 'justify-start'
                  }`}
                >
                  <div
                    className={`max-w-xs lg:max-w-md px-4 py-2 rounded-lg ${
                      message.type === 'user'
                        ? 'bg-blue-500 text-white'
                        : 'bg-gray-200 text-gray-800'
                    }`}
                  >
                    <div className="text-sm">{message.content}</div>
                    <div className="text-xs opacity-75 mt-1">
                      {message.timestamp.toLocaleTimeString()}
                    </div>
                  </div>
                </div>
              ))
            )}
            
            {/* Current transcript */}
            {currentTranscript && (
              <div className="flex justify-start">
                <div className="max-w-xs lg:max-w-md px-4 py-2 rounded-lg bg-gray-100 text-gray-600 border-2 border-dashed border-gray-300">
                  <div className="text-sm">{currentTranscript}</div>
                </div>
              </div>
            )}
            
            <div ref={conversationEndRef} />
          </div>
        </div>
      </div>
    </div>
  );
}