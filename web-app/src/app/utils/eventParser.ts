
/**
 * EventParser class for handling ADK event parsing based on author, function calls, and event state
 */

export interface ADKEventData {
  event_id: string;
  author: string;
  timestamp: number;
  is_final: boolean;
  function_call?: {
    name: string;
    args: any;
  };
  function_response?: {
    name: string;
    response: string;
  };
  has_text_content?: boolean;
  content?: {
    parts: Array<{
      text?: string;
    }>;
  };
}

export interface ParsedEventResult {
  processingStatus?: string;
  mathJaxContent?: string;
  shouldUpdateMathJax?: boolean;
  analysisComplete?: boolean;
  clearProcessingStatus?: boolean;
  visualizationConfig?: any;
  shouldShowVisualization?: boolean;
  imageUrl?: string;
  shouldUpdateImage?: boolean;
}

export class EventParser {
  /**
   * Parse an ADK event and return appropriate state updates
   */
  static parseEvent(eventData: ADKEventData): ParsedEventResult {
    const { author, is_final, function_call, function_response, has_text_content, content } = eventData;
    
    console.log(`🔍 EventParser: Processing event from ${author}, final: ${is_final}, func_call: ${!!function_call}, func_response: ${!!function_response}, text: ${has_text_content}`);
    
    const result: ParsedEventResult = {};
    
    // Handle function calls (tool usage)
    if (function_call) {
      result.processingStatus = this.getFunctionCallStatus(function_call, author);
      return result;
    }
    
    // Handle function responses (tool results)
    if (function_response) {
      result.processingStatus = this.getFunctionResponseStatus(function_response, author);
      return result;
    }
    
    // Handle text content based on author and finality
    if (has_text_content) {
      return this.parseTextContent(author, is_final, content);
    }
    
    return result;
  }
  
  /**
   * Get processing status for function calls
   */
  private static getFunctionCallStatus(functionCall: { name: string; args: any }, author: string): string {
    switch (functionCall.name) {
      case 'take_picture_and_analyze_tool':
        return "Checking your work...";
      default:
        return `Working on it...`;
    }
  }
  
  /**
   * Get processing status for function responses
   */
  private static getFunctionResponseStatus(functionResponse: { name: string; response: string }, author: string): string {
    switch (functionResponse.name) {
      case 'take_picture_and_analyze_tool':
        return "Thinking...";
      default:
        return `Processing...`;
    }
  }
  
  /**
   * Parse text content based on author and finality
   */
  private static parseTextContent(author: string, isFinal: boolean, content?: { parts: Array<{ text?: string }> }): ParsedEventResult {
    const result: ParsedEventResult = {};
    
    switch (author) {
      case 'StateEstablisher':
        return this.parseStateEstablisherContent(isFinal, content, result);
      
      case 'HelpTriageAgent':
        return this.parseHelpTriageAgentContent(isFinal, content, result);
      
      case 'HintAgent':
        return this.parseHintAgentContent(isFinal, content, result);
      
      case 'VisualizerAgent':
        return this.parseVisualizerAgentContent(isFinal, content, result);
      
      case 'expert_help_agent':
        return this.parseExpertHelpAgentContent(isFinal, content, result);
      
      case 'homework_tutor':
        return this.parseHomeworkTutorContent(isFinal, content, result);
      
      default:
        // For unknown authors, don't update status to avoid jumpiness
        // Only log for debugging
        console.log(`🔍 Unknown event author: ${author}, final: ${isFinal}`);
        return result; // Return empty result - no status update
    }
  }
  
  /**
   * Parse StateEstablisher content - handles problem state and MathJax
   */
  private static parseStateEstablisherContent(isFinal: boolean, content?: { parts: Array<{ text?: string }> }, result: ParsedEventResult = {}): ParsedEventResult {
    // Only update status for significant state changes
    if (isFinal) {
      result.processingStatus = "Problem identified!";
      // Don't auto-clear - let it stay until HintAgent provides final response
    } else {
      // Only show status during non-final events if it's meaningful
      result.processingStatus = "Understanding your problem...";
    }
    
    return result;
  }
  
  /**
   * Parse HintAgent content - handles hints and guidance
   */
  private static parseHintAgentContent(isFinal: boolean, content?: { parts: Array<{ text?: string }> }, result: ParsedEventResult = {}): ParsedEventResult {
    if (isFinal) {
      result.processingStatus = "Ready to help!";
      result.analysisComplete = true;
      result.clearProcessingStatus = true; // Clear after a short delay
      
      // Check if content contains MathJax that should be displayed
      const textContent = this.extractTextContent(content);
      if (textContent) {
        console.log('🔍 HintAgent final content from backend:', textContent);
        
        // Backend has already cleaned and parsed the JSON, so we can use it directly
        // Try to parse as JSON first (for structured responses that backend processed)
        try {
          const jsonResponse = JSON.parse(textContent);
          if (jsonResponse && typeof jsonResponse === 'object') {
            // Handle structured JSON response with specific fields
            if (jsonResponse.mathjax_content) {
              console.log('🔍 HintAgent JSON contains mathjax_content field');
              result.mathJaxContent = this.normalizeMathJax(jsonResponse.mathjax_content);
              result.shouldUpdateMathJax = true;
            }
            
            // Handle image URLs
            if (jsonResponse.image_url) {
              console.log('🔍 HintAgent JSON contains image_url field:', jsonResponse.image_url);
              result.imageUrl = this.convertSessionUrlToBackendUrl(jsonResponse.image_url);
              result.shouldUpdateImage = true;
            }
            
            // help_text is handled by the live agent audio, not the frontend display
          }
        } catch (e) {
          // Handle as plain text if not valid JSON
          if (textContent.includes('$') || textContent.includes('\\')) {
            console.log('🔍 HintAgent content contains MathJax');
            result.mathJaxContent = this.normalizeMathJax(textContent);
            result.shouldUpdateMathJax = true;
          }
        }
      }
    } else {
      // Only show intermediate status for HintAgent if it's meaningful
      result.processingStatus = "Analyzing your work...";
    }
    
    return result;
  }
  
  /**
   * Parse expert_help_agent content - handles expert analysis workflow
   */
  private static parseExpertHelpAgentContent(isFinal: boolean, content?: { parts: Array<{ text?: string }> }, result: ParsedEventResult = {}): ParsedEventResult {
    if (isFinal) {
      result.processingStatus = "Analysis complete!";
      result.analysisComplete = true;
      result.clearProcessingStatus = true;
    } else {
      // Don't update status for intermediate expert help events to avoid jumpiness
      // The StateEstablisher and HintAgent will provide more specific status updates
    }
    
    return result;
  }

  /**
   * Parse HelpTriageAgent content - handles decision making between hint and visualization
   */
  private static parseHelpTriageAgentContent(isFinal: boolean, content?: { parts: Array<{ text?: string }> }, result: ParsedEventResult = {}): ParsedEventResult {
    if (isFinal) {
      result.processingStatus = "Solution ready!";
      result.analysisComplete = true;
      result.clearProcessingStatus = true;
    } else {
      result.processingStatus = "Choosing best approach...";
    }
    
    return result;
  }

  /**
   * Parse VisualizerAgent content - handles visualization generation
   */
  private static parseVisualizerAgentContent(isFinal: boolean, content?: { parts: Array<{ text?: string }> }, result: ParsedEventResult = {}): ParsedEventResult {
    if (isFinal) {
      result.processingStatus = "Visualization ready!";
      result.analysisComplete = true;
      result.clearProcessingStatus = true;
      
      // Check if content contains visualization configuration
      const textContent = this.extractTextContent(content);
      if (textContent) {
        console.log('🔍 VisualizerAgent final content:', textContent);
        
        try {
          const jsonResponse = JSON.parse(textContent);
          if (jsonResponse && typeof jsonResponse === 'object' && jsonResponse.chart_config) {
            console.log('🔍 VisualizerAgent contains chart configuration');
            result.visualizationConfig = jsonResponse;
            result.shouldShowVisualization = true;
          }
        } catch (e) {
          console.log('🔍 VisualizerAgent content not valid JSON:', e);
        }
      }
    } else {
      result.processingStatus = "Creating visualization...";
    }
    
    return result;
  }

  /**
   * Parse homework_tutor content - handles main live agent
   */
  private static parseHomeworkTutorContent(isFinal: boolean, content?: { parts: Array<{ text?: string }> }, result: ParsedEventResult = {}): ParsedEventResult {
    // The homework_tutor is the main live agent that coordinates everything
    // We generally don't want to show status from this agent as it can be confusing
    // The expert help agents provide better status updates
    return result; // No status updates from main tutor agent
  }
  

  /**
   * Helper method to extract text content from event parts
   */
  static extractTextContent(content?: { parts: Array<{ text?: string }> }): string {
    if (!content || !content.parts) return '';
    
    return content.parts
      .map(part => part.text || '')
      .filter(text => text.trim())
      .join(' ')
      .trim();
  }


  /**
   * Normalize MathJax expressions to ensure proper rendering
   */
  private static normalizeMathJax(content: string): string {
    // Ensure proper escaping for MathJax delimiters
    let normalized = content;
    
    // Fix common MathJax issues
    normalized = normalized.replace(/\\\\/g, '\\');
    
    return normalized;
  }

  /**
   * Convert session:sessionId URLs to proper backend URLs
   */
  private static convertSessionUrlToBackendUrl(imageUrl: string): string {
    if (imageUrl && imageUrl.startsWith('session:')) {
      const sessionId = imageUrl.replace('session:', '');
      return `http://localhost:8000/sessions/${sessionId}/image`;
    }
    return imageUrl;
  }
}
