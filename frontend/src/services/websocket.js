/**
 * WebSocket client for voice input
 */

const WS_BASE_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000';

/**
 * Create WebSocket connection for voice transcriptions
 */
export function createWebSocketConnection(onMessage, onError) {
  const ws = new WebSocket(`${WS_BASE_URL}/ws/voice`);

  ws.onopen = () => {
    console.log('WebSocket connected');
  };

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      onMessage(data);
    } catch (error) {
      console.error('Error parsing WebSocket message:', error);
    }
  };

  ws.onerror = (error) => {
    console.error('WebSocket error:', error);
    if (onError) {
      onError(error);
    }
  };

  ws.onclose = () => {
    console.log('WebSocket disconnected');
  };

  return ws;
}

/**
 * Send voice transcription to WebSocket
 */
export function sendTranscription(ws, text) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ text }));
  } else {
    console.error('WebSocket is not open');
  }
}

