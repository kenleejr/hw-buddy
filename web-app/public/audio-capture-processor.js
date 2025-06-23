class AudioCaptureProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.audioDataCount = 0;
  }

  process(inputs, outputs, parameters) {
    const input = inputs[0];
    this.audioDataCount++;
    
    if (input && input.length > 0) {
      const inputChannel = input[0]; // Get first channel (mono)
      
      if (inputChannel && inputChannel.length > 0) {
        // Calculate audio level for debugging
        let sum = 0;
        for (let i = 0; i < inputChannel.length; i++) {
          sum += Math.abs(inputChannel[i]);
        }
        const avgLevel = sum / inputChannel.length;
        
        // Send audio data and level info to main thread
        this.port.postMessage({
          type: 'audioData',
          audioData: inputChannel,
          level: avgLevel,
          count: this.audioDataCount
        });
      }
    }
    
    // Keep processor alive
    return true;
  }
}

registerProcessor('audio-capture-processor', AudioCaptureProcessor);