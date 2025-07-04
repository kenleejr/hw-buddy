/**
 * Audio utilities for backend communication
 * Updated for WebSocket-based audio streaming without Gemini Live dependencies
 */

/**
 * Encode bytes to base64 string
 */
function encode(bytes: Uint8Array): string {
  let binary = '';
  const len = bytes.byteLength;
  for (let i = 0; i < len; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}

/**
 * Decode base64 string to bytes
 */
function decode(base64: string): Uint8Array {
  const binaryString = atob(base64);
  const len = binaryString.length;
  const bytes = new Uint8Array(len);
  for (let i = 0; i < len; i++) {
    bytes[i] = binaryString.charCodeAt(i);
  }
  return bytes;
}

/**
 * Convert Float32Array audio data to base64 PCM format for backend
 */
function encodeAudioForBackend(data: Float32Array): string {
  const int16Array = new Int16Array(data.length);
  for (let i = 0; i < data.length; i++) {
    // Convert float32 -1 to 1 to int16 -32768 to 32767
    int16Array[i] = Math.max(-32768, Math.min(32767, data[i] * 32768));
  }

  return encode(new Uint8Array(int16Array.buffer));
}

/**
 * Decode audio data from backend to AudioBuffer
 */
async function decodeAudioFromBackend(
  data: Uint8Array,
  ctx: AudioContext,
  sampleRate: number,
  numChannels: number,
): Promise<AudioBuffer> {
  const buffer = ctx.createBuffer(
    numChannels,
    data.length / 2 / numChannels,
    sampleRate,
  );

  const dataInt16 = new Int16Array(data.buffer);
  const dataFloat32 = new Float32Array(dataInt16.length);
  
  for (let i = 0; i < dataInt16.length; i++) {
    dataFloat32[i] = dataInt16[i] / 32768.0;
  }

  // Handle channel mapping
  if (numChannels === 1) {
    buffer.copyToChannel(dataFloat32, 0);
  } else {
    // Extract interleaved channels
    for (let i = 0; i < numChannels; i++) {
      const channel = dataFloat32.filter(
        (_, index) => index % numChannels === i,
      );
      buffer.copyToChannel(channel, i);
    }
  }

  return buffer;
}

/**
 * Create PCM blob format for backend communication
 */
interface AudioBlob {
  data: string;
  mimeType: string;
}

function createPCMBlob(data: Float32Array, sampleRate: number = 16000): AudioBlob {
  return {
    data: encodeAudioForBackend(data),
    mimeType: `audio/pcm;rate=${sampleRate}`,
  };
}

/**
 * Audio level calculation for UI feedback
 */
function calculateAudioLevel(audioData: Float32Array): number {
  let sum = 0;
  for (let i = 0; i < audioData.length; i++) {
    sum += audioData[i] * audioData[i];
  }
  return Math.sqrt(sum / audioData.length);
}

/**
 * Audio format conversion utilities
 */
class AudioConverter {
  static float32ToInt16(float32Array: Float32Array): Int16Array {
    const int16Array = new Int16Array(float32Array.length);
    for (let i = 0; i < float32Array.length; i++) {
      int16Array[i] = Math.max(-32768, Math.min(32767, float32Array[i] * 32768));
    }
    return int16Array;
  }

  static int16ToFloat32(int16Array: Int16Array): Float32Array {
    const float32Array = new Float32Array(int16Array.length);
    for (let i = 0; i < int16Array.length; i++) {
      float32Array[i] = int16Array[i] / 32768.0;
    }
    return float32Array;
  }

  static resampleAudio(
    inputData: Float32Array, 
    inputRate: number, 
    outputRate: number
  ): Float32Array {
    if (inputRate === outputRate) {
      return inputData;
    }

    const ratio = inputRate / outputRate;
    const outputLength = Math.floor(inputData.length / ratio);
    const outputData = new Float32Array(outputLength);

    for (let i = 0; i < outputLength; i++) {
      const inputIndex = i * ratio;
      const inputIndexFloor = Math.floor(inputIndex);
      const inputIndexCeil = Math.min(inputIndexFloor + 1, inputData.length - 1);
      const t = inputIndex - inputIndexFloor;
      
      // Linear interpolation
      outputData[i] = inputData[inputIndexFloor] * (1 - t) + inputData[inputIndexCeil] * t;
    }

    return outputData;
  }
}

/**
 * Audio quality utilities
 */
class AudioQuality {
  static detectClipping(audioData: Float32Array, threshold: number = 0.98): boolean {
    for (let i = 0; i < audioData.length; i++) {
      if (Math.abs(audioData[i]) >= threshold) {
        return true;
      }
    }
    return false;
  }

  static calculateSNR(audioData: Float32Array): number {
    // Simple SNR estimation based on signal variance
    let sum = 0;
    let sumSquares = 0;
    
    for (let i = 0; i < audioData.length; i++) {
      sum += audioData[i];
      sumSquares += audioData[i] * audioData[i];
    }
    
    const mean = sum / audioData.length;
    const variance = (sumSquares / audioData.length) - (mean * mean);
    
    return variance > 0 ? 10 * Math.log10(variance) : -Infinity;
  }
}

export {
  encode,
  decode,
  encodeAudioForBackend,
  decodeAudioFromBackend,
  createPCMBlob,
  calculateAudioLevel,
  AudioConverter,
  AudioQuality,
  type AudioBlob,
};