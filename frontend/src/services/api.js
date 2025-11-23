/**
 * API client functions for communicating with the backend
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

/**
 * List available Excel files
 */
export async function listFiles() {
  const response = await fetch(`${API_BASE_URL}/api/files`);
  if (!response.ok) {
    throw new Error(`Failed to list files: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Analyze question (non-streaming)
 */
export async function analyze(question) {
  const response = await fetch(`${API_BASE_URL}/api/analyze?question=${encodeURIComponent(question)}`);
  if (!response.ok) {
    throw new Error(`Analysis failed: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Create SSE connection for streaming analysis
 */
export function createSSEConnection(question, onMessage, onError) {
  const eventSource = new EventSource(
    `${API_BASE_URL}/api/analyze/stream?question=${encodeURIComponent(question)}`
  );

  // Handle all event types
  const handleEvent = (event) => {
    try {
      const data = JSON.parse(event.data);
      // Ensure type is set (from event type or data.type)
      if (!data.type && event.type) {
        data.type = event.type;
      }
      onMessage(data);
    } catch (error) {
      console.error('Error parsing SSE message:', error);
    }
  };

  // Listen to specific event types
  const eventTypes = ['status', 'file_selected', 'code_chunk', 'execution_result', 
                      'column_traceability', 'complete', 'error'];
  
  eventTypes.forEach(eventType => {
    eventSource.addEventListener(eventType, handleEvent);
  });

  // Also handle default message events
  eventSource.onmessage = handleEvent;

  eventSource.onerror = (error) => {
    // Only trigger error if connection is actually closed
    // SSE can have temporary errors that don't mean failure
    if (eventSource.readyState === EventSource.CLOSED) {
      console.error('SSE connection closed:', error);
      // Don't close again if already closed
      if (onError) {
        onError(error);
      }
    } else if (eventSource.readyState === EventSource.CONNECTING) {
      // Connection is trying to reconnect - this is the issue!
      // Close it to prevent automatic reconnection
      console.warn('SSE attempting to reconnect - closing to prevent infinite requests');
      eventSource.close();
      if (onError) {
        onError(error);
      }
    } else {
      // Connection is still open, just log the error
      console.warn('SSE temporary error (connection still open):', error);
    }
  };

  return eventSource;
}

