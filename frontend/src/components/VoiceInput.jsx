import React, { useState, useEffect, useRef } from 'react';
import { createWebSocketConnection, sendTranscription } from '../services/websocket';

/**
 * Voice input component using Web Speech API
 */
export default function VoiceInput({ onTranscription, onAnalysisResult, onQuestion, onStartLoading, onResetState }) {
  const [isListening, setIsListening] = useState(false);
  const [status, setStatus] = useState('');
  const recognitionRef = useRef(null);
  const wsRef = useRef(null);

  useEffect(() => {
    // Initialize Web Speech API
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    
    if (!SpeechRecognition) {
      setStatus('Speech recognition not supported in this browser');
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = 'zh-CN,en-US'; // Support Chinese and English

    recognition.onstart = () => {
      setIsListening(true);
      setStatus('Listening...');
    };

    recognition.onresult = (event) => {
      let interimTranscript = '';
      let finalTranscript = '';

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          finalTranscript += transcript + ' ';
        } else {
          interimTranscript += transcript;
        }
      }

      if (finalTranscript) {
        const text = finalTranscript.trim();
        
        // Only send if we have meaningful text
        if (text && text.length >= 3) {
          setStatus(`Heard: ${text}`);
          
          // Reset state before starting new analysis
          if (onResetState) {
            onResetState();
          }
          
          // Set question for display
          if (onQuestion) {
            onQuestion(text);
          }
          
          // Start loading state
          if (onStartLoading) {
            onStartLoading(true);
          }
          
          // Send to WebSocket
          if (wsRef.current) {
            sendTranscription(wsRef.current, text);
          }
          
          if (onTranscription) {
            onTranscription(text);
          }
        } else {
          setStatus('No clear speech detected. Please try again.');
        }
      } else if (interimTranscript) {
        setStatus(`Listening: ${interimTranscript}`);
      }
    };

    recognition.onerror = (event) => {
      console.error('Speech recognition error:', event.error);
      // Handle specific error types
      if (event.error === 'no-speech') {
        setStatus('No speech detected. Please try again.');
      } else if (event.error === 'audio-capture') {
        setStatus('No microphone found. Please check your microphone settings.');
      } else if (event.error === 'not-allowed') {
        setStatus('Microphone permission denied. Please allow microphone access.');
      } else {
        setStatus(`Error: ${event.error}`);
      }
      setIsListening(false);
    };

    recognition.onend = () => {
      setIsListening(false);
      setStatus('');
    };

    recognitionRef.current = recognition;

    // Don't initialize WebSocket connection until user starts voice input
    // WebSocket will be created when startListening is called

    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.stop();
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [onTranscription, onAnalysisResult]);

  const startListening = () => {
    if (recognitionRef.current && !isListening) {
      // Initialize WebSocket connection only when starting voice input
      if (!wsRef.current || wsRef.current.readyState === WebSocket.CLOSED) {
        wsRef.current = createWebSocketConnection(
          (data) => {
            // Handle WebSocket messages
            if (data.type === 'code_chunk') {
              if (onAnalysisResult) {
                onAnalysisResult({ type: 'code_chunk', chunk: data.chunk });
              }
            } else if (data.type === 'execution_result') {
              if (onAnalysisResult) {
                onAnalysisResult({ type: 'execution_result', ...data });
              }
            } else if (data.type === 'column_traceability') {
              if (onAnalysisResult) {
                onAnalysisResult({ type: 'column_traceability', ...data });
              }
            } else if (data.type === 'complete') {
              setStatus('Analysis complete');
              if (onStartLoading) {
                onStartLoading(false);
              }
            } else if (data.type === 'error') {
              setStatus(`Error: ${data.error}`);
              if (onAnalysisResult) {
                onAnalysisResult({ type: 'error', error: data.error });
              }
              if (onStartLoading) {
                onStartLoading(false);
              }
            }
          },
          (error) => {
            console.error('WebSocket error:', error);
            setStatus('WebSocket connection error');
          }
        );
      }
      recognitionRef.current.start();
    }
  };

  const stopListening = () => {
    if (recognitionRef.current && isListening) {
      recognitionRef.current.stop();
    }
  };

  return (
    <div className="voice-input">
      <div className="button-group">
        <button
          className={`btn ${isListening ? 'btn-danger' : 'btn-secondary'}`}
          onClick={isListening ? stopListening : startListening}
        >
          {isListening ? 'Stop Recording' : 'Start Voice Input'}
        </button>
      </div>
      {status && (
        <div className={`voice-status ${isListening ? 'listening' : ''}`}>
          {status}
        </div>
      )}
    </div>
  );
}

