import React, { useState, useCallback, useEffect, useRef } from 'react';
import TextInput from './components/TextInput';
import VoiceInput from './components/VoiceInput';
import CodeDisplay from './components/CodeDisplay';
import ResultsDisplay from './components/ResultsDisplay';
import ColumnTraceability from './components/ColumnTraceability';
import GraphDisplay from './components/GraphDisplay';
import { createSSEConnection } from './services/api';

/**
 * Main App component
 */
export default function App() {
  const [code, setCode] = useState('');
  const [output, setOutput] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [columns, setColumns] = useState([]);
  const [originalFile, setOriginalFile] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [status, setStatus] = useState('');
  const [question, setQuestion] = useState('');
  const [graphFiles, setGraphFiles] = useState([]);
  const [isComplete, setIsComplete] = useState(false);
  const [sseStreamClosed, setSseStreamClosed] = useState(false);
  const sseConnectionRef = useRef(null);
  const renderCheckTimeoutRef = useRef(null);

  // Helper to close SSE connection
  const closeSSEConnection = useCallback(() => {
    if (sseConnectionRef.current && sseConnectionRef.current.readyState !== EventSource.CLOSED) {
      sseConnectionRef.current.close();
      sseConnectionRef.current = null;
    }
  }, []);

  // Helper to clear all timeouts
  const clearAllTimeouts = useCallback(() => {
    if (renderCheckTimeoutRef.current) {
      clearTimeout(renderCheckTimeoutRef.current);
      renderCheckTimeoutRef.current = null;
    }
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      closeSSEConnection();
      clearAllTimeouts();
    };
  }, [closeSSEConnection, clearAllTimeouts]);

  // Check if analysis is complete: SSE closed, all data received, and rendering done
  useEffect(() => {
    clearAllTimeouts();

    if (isComplete || !sseStreamClosed) {
      return;
    }

    const hasAllData = code.length > 0 && (output || error) && columns.length > 0;
    
    if (hasAllData) {
      // Wait for React rendering and iframe loading
      requestAnimationFrame(() => {
        renderCheckTimeoutRef.current = setTimeout(() => {
          const streamStillClosed = !sseConnectionRef.current || 
            sseConnectionRef.current.readyState === EventSource.CLOSED;
          
          if (streamStillClosed && hasAllData) {
            setIsLoading(false);
            setIsComplete(true);
            setStatus('The analysis is complete.');
          }
        }, 1000);
      });
    }
  }, [isComplete, sseStreamClosed, code, output, error, columns, clearAllTimeouts]);

  // Reset all analysis state (without affecting loading state)
  const resetAnalysisState = useCallback(() => {
    setCode('');
    setOutput('');
    setError('');
    setSuccess(false);
    setColumns([]);
    setOriginalFile('');
    setGraphFiles([]);
    setIsComplete(false);
    setSseStreamClosed(false);
    setStatus('');
    clearAllTimeouts();
  }, [clearAllTimeouts]);

  // Handle execution result data
  const handleExecutionResult = useCallback((data) => {
    setOutput(data.output || '');
    if (data.error && !data.success) {
      setError(data.error || '');
    } else {
      setError('');
    }
    setSuccess(data.success || false);
    setGraphFiles(data.graph_files || []);
    setStatus('');
  }, []);

  const handleAnalyze = useCallback((question) => {
    // Reset state and close any existing connection
    resetAnalysisState();
    closeSSEConnection();
    
    // Start new analysis
    setQuestion(question);
    setIsLoading(true);

    // Create new SSE connection
    const eventSource = createSSEConnection(
      question,
      (data) => {
        if (data.type === 'status') {
          setStatus(data.message || '');
        } else if (data.type === 'file_selected') {
          setStatus(`Selected file: ${data.file_name}`);
        } else if (data.type === 'code_chunk') {
          setCode((prev) => prev + (data.chunk || ''));
        } else if (data.type === 'execution_result') {
          handleExecutionResult(data);
        } else if (data.type === 'column_traceability') {
          setColumns(data.columns_used || []);
          setOriginalFile(data.original_file || '');
          closeSSEConnection();
          setSseStreamClosed(true);
        } else if (data.type === 'error') {
          setError(data.error || 'An error occurred');
          setIsLoading(false);
          setIsComplete(false);
          setStatus('');
          closeSSEConnection();
          setSseStreamClosed(true);
        }
      },
      (err) => {
        console.error('SSE error:', err);
        setIsLoading(false);
        closeSSEConnection();
        setSseStreamClosed(true);
        
        // Only show connection error if we haven't received any results
        setCode((prevCode) => {
          setOutput((prevOutput) => {
            if (!prevOutput && !prevCode) {
              setError('Connection error. Please check if the backend server is running.');
            }
            return prevOutput;
          });
          return prevCode;
        });
      }
    );

    sseConnectionRef.current = eventSource;
  }, [closeSSEConnection, resetAnalysisState, handleExecutionResult]);

  const handleVoiceAnalysisResult = useCallback((data) => {
    if (data.type === 'code_chunk') {
      setCode((prev) => prev + (data.chunk || ''));
    } else if (data.type === 'execution_result') {
      handleExecutionResult(data);
    } else if (data.type === 'column_traceability') {
      setColumns(data.columns_used || []);
      setOriginalFile(data.original_file || '');
      setSseStreamClosed(true);
    } else if (data.type === 'error') {
      setError(data.error || 'An error occurred');
      setIsLoading(false);
      setIsComplete(false);
      setSseStreamClosed(true);
    } else if (data.type === 'complete') {
      setIsLoading(false);
      setIsComplete(true);
      setStatus('The analysis is complete.');
    }
  }, [handleExecutionResult]);

  return (
    <div className="app">
      <div className="header">
        <h1>Excel Agent</h1>
        <p>Natural Language Excel Data Analysis</p>
      </div>

      <div className="input-section">
        <TextInput onAnalyze={handleAnalyze} disabled={isLoading} />
        <VoiceInput
          onTranscription={handleAnalyze}
          onAnalysisResult={handleVoiceAnalysisResult}
          onQuestion={setQuestion}
          onStartLoading={setIsLoading}
          onResetState={resetAnalysisState}
        />
      </div>

      {isLoading && (
        <div className="analyzing-container">
          <div className="analyzing-animation">
            <div className="pulse-dot"></div>
            <div className="pulse-dot"></div>
            <div className="pulse-dot"></div>
          </div>
          <span className="analyzing-text">Analyzing...</span>
        </div>
      )}
      
      {status && (
        isComplete ? (
          <div className="completion-message">{status}</div>
        ) : !isLoading && (
          <div className="status-message">{status}</div>
        )
      )}

      {question && (
        <div className="question-display">
          <h3>Question</h3>
          <p>{question}</p>
        </div>
      )}

      {(code || output || error) && (
        <div className="results-section">
          <CodeDisplay code={code} />
          <ResultsDisplay output={output} error={error} success={success} />
        </div>
      )}

      {graphFiles.length > 0 && (
        <GraphDisplay graphFiles={graphFiles} />
      )}

      {columns.length > 0 && (
        <ColumnTraceability columns={columns} originalFile={originalFile} />
      )}
    </div>
  );
}

