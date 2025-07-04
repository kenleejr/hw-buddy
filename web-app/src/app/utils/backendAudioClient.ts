/**
 * Backend Audio Client for WebSocket communication
 * Handles bidirectional audio streaming with the ADK Live backend
 */

import { 
  encodeAudioForBackend, 
  decodeAudioFromBackend, 
  calculateAudioLevel 
} from './backendAudio';

export interface AudioMessage {
  type: 'audio' | 'start_recording' | 'stop_recording' | 'ping';
  data?: string | object;
}

export interface BackendMessage {
  type: 'audio' | 'agent_ready' | 'tool_call' | 'turn_complete' | 'interrupted' | 'error' | 'text' | 'image_received' | 'image_analyzed' | 'recording_started' | 'recording_stopped' | 'pong';
  data?: any;
}

export interface AudioStreamConfig {
  inputSampleRate: number;
  outputSampleRate: number;
  inputBufferSize: number;
  outputBufferSize: number;
}

const DEFAULT_CONFIG: AudioStreamConfig = {
  inputSampleRate: 16000,  // Backend expects 16kHz
  outputSampleRate: 24000, // Backend sends 24kHz
  inputBufferSize: 512,
  outputBufferSize: 1024,
};

export class BackendAudioClient {
  private websocket: WebSocket | null = null;
  private inputAudioContext: AudioContext | null = null;
  private outputAudioContext: AudioContext | null = null;
  private inputWorkletNode: AudioWorkletNode | null = null;
  private inputGainNode: GainNode | null = null;
  private outputGainNode: GainNode | null = null;
  private mediaStream: MediaStream | null = null;
  private config: AudioStreamConfig;
  private isConnected = false;
  private isRecording = false;
  private audioQueue: AudioBuffer[] = [];
  private nextPlayTime = 0;
  
  // Event handlers
  public onMessage: ((message: BackendMessage) => void) | null = null;
  public onAudioLevel: ((level: number) => void) | null = null;
  public onConnectionChange: ((connected: boolean) => void) | null = null;
  public onError: ((error: string) => void) | null = null;

  constructor(config: Partial<AudioStreamConfig> = {}) {
    this.config = { ...DEFAULT_CONFIG, ...config };
  }

  /**
   * Connect to the backend WebSocket
   */
  async connect(sessionId: string, backendUrl: string = 'ws://localhost:8000'): Promise<void> {
    try {
      // Close existing connection
      if (this.websocket) {
        this.disconnect();
      }

      // Initialize audio contexts
      await this.initializeAudio();

      // Connect WebSocket
      const wsUrl = `${backendUrl}/ws/audio/${sessionId}`;
      console.log('🔌 Connecting to WebSocket:', wsUrl);
      
      this.websocket = new WebSocket(wsUrl);
      
      this.websocket.onopen = () => {
        console.log('🔌 WebSocket connected');
        this.isConnected = true;
        this.onConnectionChange?.(true);
      };

      this.websocket.onmessage = (event) => {
        try {
          const message: BackendMessage = JSON.parse(event.data);
          this.handleBackendMessage(message);
        } catch (error) {
          console.error('🔌 Error parsing WebSocket message:', error);
          this.onError?.('Error parsing WebSocket message');
        }
      };

      this.websocket.onerror = (error) => {
        console.error('🔌 WebSocket error:', error);
        this.onError?.('WebSocket connection error');
      };

      this.websocket.onclose = (event) => {
        console.log('🔌 WebSocket closed:', event.code, event.reason);
        this.isConnected = false;
        this.onConnectionChange?.(false);
      };

      // Wait for connection
      await this.waitForConnection();
      
    } catch (error) {
      console.error('🔌 Error connecting to backend:', error);
      throw error;
    }
  }

  /**
   * Initialize audio contexts and worklet
   */
  private async initializeAudio(): Promise<void> {
    try {
      // Create audio contexts
      this.inputAudioContext = new (window.AudioContext || (window as any).webkitAudioContext)({
        sampleRate: this.config.inputSampleRate
      });
      
      this.outputAudioContext = new (window.AudioContext || (window as any).webkitAudioContext)({
        sampleRate: this.config.outputSampleRate
      });

      // Load audio worklet for input processing
      await this.inputAudioContext.audioWorklet.addModule('/audio-capture-processor.js');

      // Create gain nodes
      this.inputGainNode = this.inputAudioContext.createGain();
      this.outputGainNode = this.outputAudioContext.createGain();
      
      // Connect output gain to destination
      this.outputGainNode.connect(this.outputAudioContext.destination);
      
      this.nextPlayTime = this.outputAudioContext.currentTime;

      console.log('🎵 Audio contexts initialized');
      
    } catch (error) {
      console.error('🎵 Error initializing audio:', error);
      throw error;
    }
  }

  /**
   * Start recording audio
   */
  async startRecording(): Promise<void> {
    if (!this.isConnected || this.isRecording) {
      throw new Error('Cannot start recording: not connected or already recording');
    }

    try {
      // Resume audio contexts
      if (this.inputAudioContext?.state === 'suspended') {
        await this.inputAudioContext.resume();
      }
      if (this.outputAudioContext?.state === 'suspended') {
        await this.outputAudioContext.resume();
      }

      // Get microphone access
      this.mediaStream = await navigator.mediaDevices.getUserMedia({ 
        audio: {
          sampleRate: this.config.inputSampleRate,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        }
      });

      // Create audio chain
      const source = this.inputAudioContext!.createMediaStreamSource(this.mediaStream);
      source.connect(this.inputGainNode!);

      // Create worklet node for processing
      this.inputWorkletNode = new AudioWorkletNode(
        this.inputAudioContext!,
        'audio-capture-processor'
      );

      this.inputGainNode!.connect(this.inputWorkletNode);
      this.inputWorkletNode.connect(this.inputAudioContext!.destination);

      // Handle audio data from worklet
      this.inputWorkletNode.port.onmessage = (event) => {
        const { type, audioData, level } = event.data;
        
        if (type === 'audioData' && this.isRecording) {
          // Calculate and update audio level for UI
          const calculatedLevel = calculateAudioLevel(audioData);
          this.onAudioLevel?.(calculatedLevel * 100);
          
          // Convert Float32Array to base64 and send to backend
          const audioBlob = this.encodeAudioData(audioData);
          this.sendMessage({
            type: 'audio',
            data: audioBlob
          });
        }
      };

      this.isRecording = true;
      
      // Notify backend
      this.sendMessage({ type: 'start_recording' });
      
      console.log('🎤 Recording started');
      
    } catch (error) {
      console.error('🎤 Error starting recording:', error);
      throw error;
    }
  }

  /**
   * Stop recording audio
   */
  stopRecording(): void {
    if (!this.isRecording) return;

    this.isRecording = false;

    // Stop media stream
    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach(track => track.stop());
      this.mediaStream = null;
    }

    // Disconnect worklet
    if (this.inputWorkletNode) {
      this.inputWorkletNode.disconnect();
      this.inputWorkletNode = null;
    }

    // Reset audio level
    this.onAudioLevel?.(0);

    // Notify backend
    this.sendMessage({ type: 'stop_recording' });

    console.log('🎤 Recording stopped');
  }

  /**
   * Handle incoming messages from backend
   */
  private handleBackendMessage(message: BackendMessage): void {
    console.log('🔌 Received message:', message.type);

    switch (message.type) {
      case 'audio':
        this.handleIncomingAudio(message.data);
        break;
        
      case 'agent_ready':
      case 'tool_call':
      case 'turn_complete':
      case 'interrupted':
      case 'error':
      case 'text':
      case 'image_received':
      case 'image_analyzed':
      case 'recording_started':
      case 'recording_stopped':
        this.onMessage?.(message);
        break;
        
      case 'pong':
        // Handle ping response
        break;
        
      default:
        console.log('🔌 Unknown message type:', message.type);
    }
  }

  /**
   * Handle incoming audio from backend
   */
  private async handleIncomingAudio(base64Audio: string): Promise<void> {
    try {
      if (!this.outputAudioContext) return;

      // Decode base64 to binary
      const binaryString = atob(base64Audio);
      const bytes = new Uint8Array(binaryString.length);
      for (let i = 0; i < binaryString.length; i++) {
        bytes[i] = binaryString.charCodeAt(i);
      }

      // Convert to AudioBuffer
      const audioBuffer = await this.decodeAudioData(
        bytes,
        this.outputAudioContext,
        this.config.outputSampleRate,
        1
      );

      // Schedule playback
      this.scheduleAudioPlayback(audioBuffer);
      
    } catch (error) {
      console.error('🔊 Error handling incoming audio:', error);
    }
  }

  /**
   * Schedule audio playback
   */
  private scheduleAudioPlayback(audioBuffer: AudioBuffer): void {
    if (!this.outputAudioContext || !this.outputGainNode) return;

    try {
      const source = this.outputAudioContext.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(this.outputGainNode);

      // Schedule playback
      this.nextPlayTime = Math.max(
        this.nextPlayTime,
        this.outputAudioContext.currentTime
      );

      source.start(this.nextPlayTime);
      this.nextPlayTime += audioBuffer.duration;

      source.onended = () => {
        // Cleanup when playback ends
      };

    } catch (error) {
      console.error('🔊 Error scheduling audio playback:', error);
    }
  }

  /**
   * Encode audio data for transmission
   */
  private encodeAudioData(audioData: Float32Array): string {
    return encodeAudioForBackend(audioData);
  }

  /**
   * Decode audio data from backend
   */
  private async decodeAudioData(
    data: Uint8Array,
    context: AudioContext,
    sampleRate: number,
    channels: number
  ): Promise<AudioBuffer> {
    return await decodeAudioFromBackend(data, context, sampleRate, channels);
  }

  /**
   * Send message to backend
   */
  private sendMessage(message: AudioMessage): void {
    if (!this.websocket || this.websocket.readyState !== WebSocket.OPEN) {
      console.warn('🔌 Cannot send message: WebSocket not connected');
      return;
    }

    try {
      this.websocket.send(JSON.stringify(message));
    } catch (error) {
      console.error('🔌 Error sending message:', error);
      this.onError?.('Error sending message to backend');
    }
  }

  /**
   * Send ping to keep connection alive
   */
  ping(): void {
    this.sendMessage({ type: 'ping' });
  }

  /**
   * Wait for WebSocket connection
   */
  private waitForConnection(): Promise<void> {
    return new Promise((resolve, reject) => {
      if (!this.websocket) {
        reject(new Error('WebSocket not initialized'));
        return;
      }

      if (this.websocket.readyState === WebSocket.OPEN) {
        resolve();
        return;
      }

      const timeout = setTimeout(() => {
        reject(new Error('Connection timeout'));
      }, 10000);

      this.websocket.onopen = () => {
        clearTimeout(timeout);
        console.log('🔌 WebSocket connected');
        this.isConnected = true;
        this.onConnectionChange?.(true);
        resolve();
      };

      this.websocket.onerror = () => {
        clearTimeout(timeout);
        reject(new Error('Connection failed'));
      };
    });
  }

  /**
   * Disconnect from backend
   */
  disconnect(): void {
    this.stopRecording();

    if (this.websocket) {
      this.websocket.close();
      this.websocket = null;
    }

    if (this.inputAudioContext) {
      this.inputAudioContext.close();
      this.inputAudioContext = null;
    }

    if (this.outputAudioContext) {
      this.outputAudioContext.close();
      this.outputAudioContext = null;
    }

    this.isConnected = false;
    this.onConnectionChange?.(false);

    console.log('🔌 Disconnected from backend');
  }

  /**
   * Get connection status
   */
  get connected(): boolean {
    return this.isConnected;
  }

  /**
   * Get recording status
   */
  get recording(): boolean {
    return this.isRecording;
  }
}