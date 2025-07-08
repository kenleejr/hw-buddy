
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
      
      case 'HintAgent':
        return this.parseHintAgentContent(isFinal, content, result);
      
      case 'root_agent':
        return this.parseRootAgentContent(isFinal, content, result);
      
      default:
        // Generic handling for unknown authors
        if (isFinal) {
          result.processingStatus = "Ready!";
          result.analysisComplete = true;
        } else {
          result.processingStatus = "Thinking...";
        }
        return result;
    }
  }
  
  /**
   * Parse StateEstablisher content - handles problem state and MathJax
   */
  private static parseStateEstablisherContent(isFinal: boolean, content?: { parts: Array<{ text?: string }> }, result: ParsedEventResult = {}): ParsedEventResult {
    if (isFinal) {
      result.processingStatus = "Problem Identified!";
      // Don't auto-clear - let it stay until next agent updates
    } else {
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
      result.processingStatus = "Preparing to help...";
    }
    
    return result;
  }
  
  /**
   * Parse root_agent content - handles final orchestration
   */
  private static parseRootAgentContent(isFinal: boolean, content?: { parts: Array<{ text?: string }> }, result: ParsedEventResult = {}): ParsedEventResult {
    if (isFinal) {
      result.processingStatus = "Ready!";
      result.analysisComplete = true;
      result.clearProcessingStatus = true;
    } else {
      result.processingStatus = "Thinking...";
    }
    
    return result;
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
}
