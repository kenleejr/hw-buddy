
"use client";

import { useEffect, useRef, useState } from 'react';
import { GoogleGenAI, LiveServerMessage, Session, Modality } from '@google/genai';
import { createBlob, decode, decodeAudioData } from '../utils/audio';
import { EventParser, ADKEventData } from '../utils/eventParser';
import { Navigation } from '@/components/ui/navigation';
import { CentralStartButton } from '@/components/ui/central-start-button';
import { ChatPanel } from '@/components/ui/chat-panel';
import { ProcessingStatus } from './ProcessingStatus';
import { MathJaxDisplay } from './MathJaxDisplay';

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
  const [websocketStatus, setWebsocketStatus] = useState('disconnected');
  const [processingStatus, setProcessingStatus] = useState('');
  const [pendingFunctionCall, setPendingFunctionCall] = useState<{id: string, name: string} | null>(null);
  const pendingFunctionCallRef = useRef<{id: string, name: string} | null>(null);

  // Debug logging for currentMathJax changes
  useEffect(() => {
    console.log('🎵 currentMathJax state changed:', currentMathJax);
  }, [currentMathJax]);

  // Auto-scroll to ProcessingStatus when MathJax content updates
  useEffect(() => {
    if (currentMathJax && processingStatusRef.current) {
      // Small delay to ensure MathJax animation completes
      setTimeout(() => {
        processingStatusRef.current?.scrollIntoView({ 
          behavior: 'smooth', 
          block: 'center',
          inline: 'nearest'
        });
      }, 50); // Delay to account for MathJax animation (500ms) + buffer
    }
  }, [currentMathJax]);

  // Auto-scroll to ProcessingStatus when it appears (even if MathJax already exists)
  useEffect(() => {
    if (processingStatus && processingStatusRef.current) {
      // Small delay to ensure processing status animation starts
      setTimeout(() => {
        processingStatusRef.current?.scrollIntoView({ 
          behavior: 'smooth', 
          block: 'center',
          inline: 'nearest'
        });
      }, 300); // Delay for processing status animation
    }
  }, [processingStatus]);
  
  const sessionRef = useRef<Session | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const inputAudioContextRef = useRef<AudioContext | null>(null);
  const outputAudioContextRef = useRef<AudioContext | null>(null);
  const inputGainRef = useRef<GainNode | null>(null);
  const outputGainRef = useRef<GainNode | null>(null);
  const workletNodeRef = useRef<AudioWorkletNode | null>(null);
  // Removed conversationEndRef as we're not auto-scrolling chat anymore
  const sourcesRef = useRef<Set<AudioBufferSourceNode>>(new Set());
  const nextStartTimeRef = useRef<number>(0);
  const websocketRef = useRef<WebSocket | null>(null);
  const processingStatusRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    initializeSession();
    return () => {
      cleanup();
    };
  }, []);

  // Removed auto-scroll for conversation to focus on MathJax display

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
    if (websocketRef.current) {
      websocketRef.current.close();
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
        model: 'gemini-2.0-flash-live-001',
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
          tools: [{
            functionDeclarations: [{
              name: "get_expert_help",
              description: "Get expert homework help by analyzing the student's work and providing tailored guidance",
              parameters: {
                type: "object",
                properties: {
                  user_ask: {
                    type: "string",
                    description: "The user's specific question or request about their homework"
                  }
                },
                required: ["user_ask"]
              }
            }]
          }],
          systemInstruction: {
            parts: [{
              text: "You are a homework buddy assistant. \
              When a user asks you anything, first respond with affirmative that you can help and then in order to help them you must call the get_expert_help function. \
              Pass the user's specific question or request as the 'user_ask' parameter to the get_expert_help function. \
              This function will analyze the student's progress and provide next steps specifically tailored to the user's request. Note: this can take some time. While waiting do not say anything. \
              Do NOT supply help outside of the results of this function's result. \
              When a response returns, simply relay the function's response to the user, as it contains pointers to the student."
            }]
          }
        },
      });
      
      sessionRef.current = session;
      
      // Initialize WebSocket connection for real-time updates
      await initializeWebSocket();
      
    } catch (err: any) {
      console.error('🎵 Failed to initialize session:', err);
      setError(`Failed to initialize: ${err.message}`);
      setStatus('Failed to connect');
    }
  };

  const initializeWebSocket = async () => {
    try {
      console.log('🔌 Initializing WebSocket connection...');
      setWebsocketStatus('connecting');
      
      const wsUrl = `ws://localhost:8000/ws/${sessionId}`;
      const ws = new WebSocket(wsUrl);
      
      ws.onopen = () => {
        console.log('🔌 WebSocket connected');
        setWebsocketStatus('connected');
        setStatus('Ask me about your homework!');
      };
      
      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          console.log('🔌 WebSocket message received:', message);
          
          handleWebSocketMessage(message);
        } catch (error) {
          console.error('🔌 Error parsing WebSocket message:', error);
        }
      };
      
      ws.onerror = (error) => {
        console.error('🔌 WebSocket error:', error);
        setWebsocketStatus('error');
        setError('WebSocket connection error');
      };
      
      ws.onclose = (event) => {
        console.log('🔌 WebSocket closed:', event.code, event.reason);
        setWebsocketStatus('disconnected');
        setStatus('WebSocket disconnected');
      };
      
      websocketRef.current = ws;
      
    } catch (error) {
      console.error('🔌 Failed to initialize WebSocket:', error);
      setWebsocketStatus('error');
      setError('Failed to connect WebSocket');
    }
  };

  const handleWebSocketMessage = (message: any) => {
    switch (message.type) {
      case 'status_update':
        console.log('🔌 Status update:', message.status, message.data);
        setProcessingStatus(message.data.message || message.status);
        
        // Update specific UI states based on status
        switch (message.status) {
          case 'connected':
            setStatus('🔗 Connected and ready');
            break;
          case 'error':
            setError(message.data.message || 'An error occurred');
            setStatus('❌ Error occurred');
            setIsAnalyzingImage(false);
            break;
        }
        break;
        
      case 'adk_event':
        console.log('🔌 ADK Event:', message.event_type, message.data);
        
        // Use EventParser to handle the event
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
        
        if (parseResult.clearProcessingStatus) {
          // Clear processing status after a delay
          setTimeout(() => {
            setProcessingStatus('');
          }, 2000);
        }
        
        break;
        
      case 'final_response':
        console.log('🔌 Final response received:', message.data);
        handleFinalResponse(message.data);
        break;
        
      default:
        console.log('🔌 Unknown message type:', message.type);
    }
  };

  const normalizeMathJaxBackslashes = (text: string): string => {
    // Function to normalize backslashes within MathJax expressions to single backslashes
    const normalizeContent = (_match: string, content: string): string => {
      // Replace multiple backslashes with single backslashes
      const normalizedContent = content.replace(/\\+/g, '\\');
      return `$$${normalizedContent}$$`;
    };
    
    // Find all MathJax expressions ($$...$$) and normalize backslashes within them
    const result = text.replace(/\$\$(.*?)\$\$/g, normalizeContent);
    console.log('🔧 normalizeMathJaxBackslashes input:', text);
    console.log('🔧 normalizeMathJaxBackslashes output:', result);
    return result;
  };

  const handleFinalResponse = (responseData: any) => {
    setIsAnalyzingImage(false);
    setProcessingStatus('');
    setStatus('✅ Analysis complete');
    
    // Update the last image URL if we got one
    if (responseData.success && responseData.image_url) {
      setLastImageUrl(responseData.image_url);
    }
    
    // Parse the JSON response from backend
    let parsedAnalysis = null;
    let helpText = responseData.image_description || 'Unable to analyze image';
    
    console.log('🎵 Raw image_description from backend:', responseData.image_description);
    
    if (responseData.success && responseData.image_description) {
      try {
        parsedAnalysis = JSON.parse(responseData.image_description);
        helpText = parsedAnalysis.help_text || responseData.image_description;
        
        console.log('🎵 Parsed analysis:', parsedAnalysis);
        console.log('🎵 MathJax content:', parsedAnalysis.mathjax_content);
        console.log('🎵 Help text:', helpText);
        
        // Update MathJax content if available
        if (parsedAnalysis.mathjax_content) {
          // Normalize backslashes for proper MathJax rendering
          const normalizedMathJax = normalizeMathJaxBackslashes(parsedAnalysis.mathjax_content);
          console.log('🎵 Setting MathJax content (normalized):', normalizedMathJax);
          setCurrentMathJax(normalizedMathJax);
        } else {
          console.log('🎵 No MathJax content found in response');
        }
      } catch (e) {
        console.log('🎵 Response is not JSON, using as plain text:', e);
        console.log('🎵 RaT content:', responseData.image_description);
        helpText = responseData.image_description;
      }
    }
    
    // Send the tool response now that we have the helpText
    // Gemini will then relay this response to the user
    console.log("This is the pending function call that should have completed")
    console.log("State:", pendingFunctionCall)
    console.log("Ref:", pendingFunctionCallRef.current)
    if (pendingFunctionCallRef.current && sessionRef.current) {
      console.log('🔌 Sending delayed tool response with helpText:', helpText);
      
      try {
        sessionRef.current.sendToolResponse({
          functionResponses: [{
            id: pendingFunctionCallRef.current.id,
            name: pendingFunctionCallRef.current.name,
            response: {
              result: {
                success: responseData.success,
                message: helpText || "Analysis complete",
                status: "completed"
              }
            }
          }]
        });
        
        // Clear the pending function call
        setPendingFunctionCall(null);
        pendingFunctionCallRef.current = null;
        console.log('🔌 Tool response sent successfully');
      } catch (error) {
        console.error('🔌 Error sending tool response:', error);
      }
    }
  };

  const handleServerMessage = async (message: LiveServerMessage) => {
    
    // Handle function calls
    const toolCall = message.toolCall;
    if (toolCall && toolCall.functionCalls) {
      console.log('🎵 Function call received:', toolCall.functionCalls);
      
      for (const functionCall of toolCall.functionCalls) {
        if (functionCall.name === 'get_expert_help') {
          console.log('🎵 Executing get_expert_help function...');
          setIsAnalyzingImage(true);
          setStatus('🤖 Getting expert help...');
          
          try {
            // Send WebSocket message instead of POST request
            if (websocketRef.current && websocketRef.current.readyState === WebSocket.OPEN) {
              const message = {
                type: 'process_query',
                user_ask: functionCall.args?.user_ask || 'Please help me with my homework'
              };
              
              websocketRef.current.send(JSON.stringify(message));
              console.log('🔌 Sent process_query via WebSocket:', message);
              
              // Store the pending function call to respond to later when we get helpText
              const pendingCall = {
                id: functionCall.id || '',
                name: functionCall.name
              };
              setPendingFunctionCall(pendingCall);
              pendingFunctionCallRef.current = pendingCall;
              console.log('🔌 Stored pending function call, will respond when helpText is received');
            } else {
              throw new Error('WebSocket not connected');
            }
            
          } catch (error) {
            console.error('🎵 Error processing via WebSocket:', error);
            setError(`Error: ${error instanceof Error ? error.message : 'Unknown error'}`);
            setIsAnalyzingImage(false);
            
            // Send error response back to Gemini
            if (sessionRef.current) {
              sessionRef.current.sendToolResponse({
                functionResponses: [{
                  id: functionCall.id,
                  name: functionCall.name,
                  response: {
                    result: {
                      success: false,
                      message: `Error processing request: ${error instanceof Error ? error.message : 'Unknown error'}`
                    }
                  }
                }]
              });
            }
            
            // Clear any pending function call since we just sent the error response
            setPendingFunctionCall(null);
            pendingFunctionCallRef.current = null;
          }
        }
      }
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
        
        {/* Main Content - Show when there's activity */}
        {(conversation.length > 0 || currentUserMessage || currentAssistantMessage || isRecording || currentMathJax) && (
          <div className="space-y-8">
            {/* MathJax Display - Front and Center */}
            <MathJaxDisplay content={currentMathJax} />
            
            {/* Processing Status - Below MathJax */}
            <ProcessingStatus ref={processingStatusRef} status={processingStatus} />
            
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
      </div>
    </div>
  );
}