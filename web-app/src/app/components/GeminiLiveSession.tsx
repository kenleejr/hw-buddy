"use client";

import { useEffect, useRef, useState } from 'react';
import { GoogleGenAI, LiveServerMessage, Session, Modality } from '@google/genai';
import { createBlob, decode, decodeAudioData } from '../utils/audio';
import { Navigation } from '@/components/ui/navigation';
import { CentralStartButton } from '@/components/ui/central-start-button';
import { ChatPanel } from '@/components/ui/chat-panel';

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
  const [audioLevel, setAudioLevel] = useState(0);
  const [lastImageUrl, setLastImageUrl] = useState<string | null>(null);
  const [currentUserMessage, setCurrentUserMessage] = useState('');
  const [currentAssistantMessage, setCurrentAssistantMessage] = useState('');
  const [isAnalyzingImage, setIsAnalyzingImage] = useState(false);
  const [currentMathJax, setCurrentMathJax] = useState('');

  // Debug logging for currentMathJax changes
  useEffect(() => {
    console.log('🎵 currentMathJax state changed:', currentMathJax);
  }, [currentMathJax]);
  
  const sessionRef = useRef<Session | null>(null);
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
    if (sessionRef.current) {
      sessionRef.current.close();
    }
  };

  const initializeSession = async () => {
    try {
      console.log('🎵 Initializing session...');
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
      
      setStatus('Connecting to Gemini Live API...');
      
      const client = new GoogleGenAI({ 
         apiKey: process.env.NEXT_PUBLIC_GEMINI_API_KEY || ""
      });
      
      const session = await client.live.connect({
        model: 'gemini-live-2.5-flash-preview',
        callbacks: {
          onopen: () => {
            setStatus('Connected! Ready to record.');
            setError('');
          },
          onmessage: async (message: LiveServerMessage) => {
            await handleServerMessage(message);
          },
          onerror: (e: ErrorEvent) => {
            console.error('🎵 Session error:', e);
            setError(`Connection error: ${e.message}`);
            setStatus('Error occurred');
          },
          onclose: (e: CloseEvent) => {
            setStatus(`Connection closed: ${e.reason}`);
          },
        },
        config: {
          responseModalities: [Modality.AUDIO],
          speechConfig: {
            voiceConfig: { prebuiltVoiceConfig: { voiceName: 'Orus' } },
          },
          inputAudioTranscription: {},
          outputAudioTranscription: {},
          tools: [
            // Google Search grounding
            { googleSearch: {} },
            // Function calling with async behavior
            {
              functionDeclarations: [{
                name: "take_picture",
                description: "Take a picture of the student's homework or workspace to better understand what they're working on",
                parameters: {
                  type: "object",
                  properties: {
                    user_question: {
                      type: "string",
                      description: "The student's specific question or what they need help with"
                    },
                    context: {
                      type: "string",
                      description: "Additional context about what the student is studying or working on"
                    }
                  },
                  required: ["user_question"]
                },
                behavior: "NON_BLOCKING"
              }]
            }
          ],
          systemInstruction: {
            parts: [{
              text: `You are an intelligent homework tutor assistant. Your goal is to provide personalized, step-by-step guidance to help students learn.

When a student asks for help:
1. If you need to see their work to provide better assistance, call the take_picture function to capture an image of their homework
2. Use Google Search when you need current information or want to verify facts
3. Provide clear, educational explanations that guide the student toward understanding
4. Break down complex problems into manageable steps
5. Encourage critical thinking by asking guiding questions
6. Use proper mathematical notation when discussing math problems

You have access to:
- take_picture: Captures the student's workspace/homework for visual analysis
- Google Search: For current information and fact verification

Always be encouraging and supportive in your tutoring approach.`
            }]
          }
        },
      });
      
      sessionRef.current = session;
      
    } catch (err: any) {
      console.error('🎵 Failed to initialize session:', err);
      setError(`Failed to initialize: ${err.message}`);
      setStatus('Failed to connect');
    }
  };

  const handleTakePictureAsync = async (functionCall: any, sessionId: string) => {
    try {
      console.log('🎵 Taking picture asynchronously...');
      
      // Call the simplified backend endpoint to trigger image capture
      const response = await fetch('http://localhost:8000/capture_image', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          session_id: sessionId,
          user_question: functionCall.args?.user_question || 'Please help me with my homework',
          context: functionCall.args?.context || ''
        }),
      });
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const result = await response.json();
      console.log('🎵 Image capture result:', result);
      
      // Update the last image URL if we got one
      if (result.success && result.image_url) {
        setLastImageUrl(result.image_url);
      }
      
      // Send function response back to Gemini with scheduling
      if (sessionRef.current) {
        sessionRef.current.sendToolResponse({
          functionResponses: [{
            id: functionCall.id,
            name: functionCall.name,
            response: {
              result: {
                success: result.success,
                message: result.message,
                image_url: result.image_url || null,
                image_gcs_url: result.image_gcs_url || null
              }
            },
            scheduling: "INTERRUPT" // Interrupt current response to provide image context
          }]
        });
        
        // If we have an image with base64 data, send it to Gemini Live
        if (result.success && result.image_data) {
          console.log('🎵 Sending image to Gemini Live for analysis');
          console.log('🎵 Image base64 length:', result.image_data.length);
          
          try {
            // Send image as inline data (base64 from backend)
            sessionRef.current.sendClientContent({
              turns: [{
                role: 'user',
                parts: [{
                  inlineData: {
                    mimeType: 'image/jpeg',
                    data: result.image_data
                  }
                }, {
                  text: `I've captured an image of my homework. ${functionCall.args?.user_question || 'Please help me understand this.'} ${functionCall.args?.context || ''}`
                }]
              }]
            });
            
            console.log('🎵 Image sent to Gemini Live for analysis');
          } catch (error) {
            console.error('🎵 Error sending image to Gemini Live:', error);
          }
        } else if (result.success && !result.image_data) {
          console.warn('🎵 Image captured but no base64 data available');
        }
      }
      
    } catch (error) {
      console.error('🎵 Error in async picture taking:', error);
      
      // Send error response back to Gemini
      if (sessionRef.current) {
        sessionRef.current.sendToolResponse({
          functionResponses: [{
            id: functionCall.id,
            name: functionCall.name,
            response: {
              result: {
                success: false,
                message: `Error taking picture: ${error instanceof Error ? error.message : 'Unknown error'}`
              }
            },
            scheduling: "WHEN_IDLE" // Don't interrupt current response for errors
          }]
        });
      }
    }
  };

  const handleServerMessage = async (message: LiveServerMessage) => {
    
    // Handle function calls
    const toolCall = message.toolCall;
    if (toolCall && toolCall.functionCalls) {
      console.log('🎵 Function call received:', toolCall.functionCalls);
      
      for (const functionCall of toolCall.functionCalls) {
        if (functionCall.name === 'take_picture') {
          console.log('🎵 Executing take_picture function (async)...');
          setIsAnalyzingImage(true);
          
          // Execute the function asynchronously without blocking the conversation
          handleTakePictureAsync(functionCall, sessionId)
            .finally(() => setIsAnalyzingImage(false));
        }
      }
    }
    
    // Handle Google Search results
    if (message.serverContent?.groundingMetadata?.webSearchQueries) {
      const queries = message.serverContent.groundingMetadata.webSearchQueries;
      console.log('🎵 Google Search queries:', queries);
      setCurrentAssistantMessage(prev => prev + ` [Searching: ${queries.join(', ')}] `);
    }
    
    if (message.serverContent?.groundingMetadata?.searchEntryPoint) {
      console.log('🎵 Search results available');
    }
    
    // Handle audio response
    const audio = message.serverContent?.modelTurn?.parts?.[0]?.inlineData;
    
    if (audio && outputAudioContextRef.current) {
      nextStartTimeRef.current = Math.max(
        nextStartTimeRef.current,
        outputAudioContextRef.current.currentTime,
      );

      try {
        const decodedData = decode(audio.data || '');
        
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
    }

    // Handle interruption
    const interrupted = message.serverContent?.interrupted;
    if (interrupted) {
      for (const source of sourcesRef.current.values()) {
        source.stop();
        sourcesRef.current.delete(source);
      }
      nextStartTimeRef.current = 0;
    }
    
    // Handle turn completion and text streaming
    if (message.serverContent?.turnComplete) {
      
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
      
    }
    
    // Handle input transcription (user speech)
    if (message.serverContent?.inputTranscription?.text) {
      setCurrentUserMessage(message.serverContent.inputTranscription.text);
    }
    
    // Handle output transcription (assistant speech)
    if (message.serverContent?.outputTranscription?.text) {
      setCurrentAssistantMessage(prev => prev + message.serverContent.outputTranscription.text);
    }
    
    // Handle text content from assistant (non-audio responses)
    const textContent = message.serverContent?.modelTurn?.parts?.find(part => part.text);
    if (textContent?.text) {
      setCurrentAssistantMessage(prev => prev + textContent.text);
    }
    
    // Handle grounding metadata or other text responses
    if (message.serverContent?.groundingMetadata?.webSearchQueries) {
      const queries = message.serverContent.groundingMetadata.webSearchQueries;
      setCurrentAssistantMessage(prev => prev + ` [Searching: ${queries.join(', ')}] `);
    }
  };

  const startRecording = async () => {
    if (!sessionRef.current || isRecording || !inputAudioContextRef.current) return;
    
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
      await outputAudioContextRef.current.resume();
      
      console.log('🎵 Audio contexts resumed - Input:', inputAudioContextRef.current.state, 'Output:', outputAudioContextRef.current.state);
      
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
      mediaStreamRef.current = stream;
      
      console.log('🎵 Media stream created:', stream);
      console.log('🎵 Audio tracks:', stream.getAudioTracks());
      console.log('🎵 Track settings:', stream.getAudioTracks()[0]?.getSettings());
      
      const source = inputAudioContextRef.current.createMediaStreamSource(stream);
      source.connect(inputGainRef.current!);
      
      // Create AudioWorkletNode
      console.log('🎵 Creating AudioWorkletNode...');
      const workletNode = new AudioWorkletNode(inputAudioContextRef.current, 'audio-capture-processor');
      workletNodeRef.current = workletNode;
      
      console.log('🎵 AudioWorkletNode created:', workletNode);
      console.log('🎵 AudioWorkletNode numberOfInputs:', workletNode.numberOfInputs);
      console.log('🎵 AudioWorkletNode numberOfOutputs:', workletNode.numberOfOutputs);
      
      console.log('🎵 Connecting audio chain: InputGain → WorkletNode → Destination');
      inputGainRef.current!.connect(workletNode);
      workletNode.connect(inputAudioContextRef.current.destination);
      
      console.log('🎵 Audio chain connected successfully');
      
      setIsRecording(true);
      setStatus('🔴 Recording... Speak now!');
      
      // Handle messages from the audio worklet (after setting isRecording = true)
      console.log('🎵 Setting up worklet message handler...');
      console.log('🎵 isRecording:', true, 'sessionRef.current:', !!sessionRef.current);
      
      workletNode.port.onmessage = (event) => {
        if (!sessionRef.current) {
          return;
        }
        
        // Check if WebSocket is still open before sending data
        const ws = (sessionRef.current as any)?.ws;
        if (ws && ws.readyState !== WebSocket.OPEN) {
          console.warn('🎵 WebSocket not open, skipping audio data');
          return;
        }
        
        const { type, audioData, level, count } = event.data;
        
        if (type === 'audioData') {
          // Update audio level for UI
          setAudioLevel(level * 100); // Scale for better visualization
          
          try {
            // Send all audio data to Gemini
            const blob = createBlob(audioData);
            sessionRef.current.sendRealtimeInput({ media: blob });
            
            // Only log occasionally when there's actual audio
            if (count % 500 === 0 && level > 0.01) {
              console.log('🎵 Audio level:', level.toFixed(4), 'sending to Gemini');
            }
          } catch (error) {
            console.error('🎵 Error sending audio to Gemini:', error);
          }
        }
      };
      
      console.log('🎵 Message handler set up successfully');
      
    } catch (err: any) {
      console.error('🎵 Error starting recording:', err);
      console.error('🎵 Error name:', err.name);
      console.error('🎵 Error message:', err.message);
      
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
    setAudioLevel(0); // Reset audio level indicator
    setStatus('Processing...');
    
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach(track => track.stop());
      mediaStreamRef.current = null;
    }
    
    if (workletNodeRef.current && inputAudioContextRef.current) {
      workletNodeRef.current.disconnect();
      workletNodeRef.current = null;
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