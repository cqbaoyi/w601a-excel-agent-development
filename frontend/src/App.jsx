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
  const sseConnectionRef = useRef(null);

  // Cleanup SSE connection on unmount
  useEffect(() => {
    return () => {
      if (sseConnectionRef.current) {
        sseConnectionRef.current.close();
        sseConnectionRef.current = null;
      }
    };
  }, []);

  const handleAnalyze = useCallback((question) => {
    // Reset state
    setCode('');
    setOutput('');
    setError('');
    setSuccess(false);
    setColumns([]);
    setOriginalFile('');
    setGraphFiles([]);
    setQuestion(question);
    setIsLoading(true);
    setStatus('Analyzing...');

    // Close existing SSE connection
    if (sseConnectionRef.current) {
      sseConnectionRef.current.close();
      sseConnectionRef.current = null;
    }

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
          setOutput(data.output || '');
          // Only set error if execution actually failed
          if (data.error && !data.success) {
            setError(data.error || '');
          } else {
            setError(''); // Clear any previous errors on success
          }
          setSuccess(data.success || false);
          setGraphFiles(data.graph_files || []);
          setIsLoading(false);
          setStatus(''); // Clear status when execution completes
        } else if (data.type === 'column_traceability') {
          setColumns(data.columns_used || []);
          setOriginalFile(data.original_file || '');
          setIsLoading(false);
          setStatus(''); // Clear status when workflow completes
          // Close SSE connection after completion to prevent reconnection
          if (eventSource && eventSource.readyState !== EventSource.CLOSED) {
            eventSource.close();
            sseConnectionRef.current = null;
          }
        } else if (data.type === 'error') {
          setError(data.error || 'An error occurred');
          setIsLoading(false);
          setStatus(''); // Clear status on error
          // Close SSE connection on error to prevent reconnection
          if (eventSource && eventSource.readyState !== EventSource.CLOSED) {
            eventSource.close();
            sseConnectionRef.current = null;
          }
        }
      },
      (err) => {
        console.error('SSE error:', err);
        setIsLoading(false);
        // Close connection on error
        if (eventSource && eventSource.readyState !== EventSource.CLOSED) {
          eventSource.close();
          sseConnectionRef.current = null;
        }
        // Only show connection error if we haven't received any results
        // Use functional updates to access current state
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
  }, []);

  const resetState = useCallback(() => {
    setCode('');
    setOutput('');
    setError('');
    setSuccess(false);
    setColumns([]);
    setOriginalFile('');
    setGraphFiles([]);
  }, []);

  const handleVoiceAnalysisResult = useCallback((data) => {
    if (data.type === 'code_chunk') {
      setCode((prev) => prev + (data.chunk || ''));
    } else if (data.type === 'execution_result') {
      setOutput(data.output || '');
      // Only set error if execution actually failed
      if (data.error && !data.success) {
        setError(data.error || '');
      } else {
        setError(''); // Clear any previous errors on success
      }
      setSuccess(data.success || false);
      setGraphFiles(data.graph_files || []);
      setIsLoading(false);
    } else if (data.type === 'column_traceability') {
      setColumns(data.columns_used || []);
      setOriginalFile(data.original_file || '');
    } else if (data.type === 'error') {
      setError(data.error || 'An error occurred');
      setIsLoading(false);
    } else if (data.type === 'complete') {
      setIsLoading(false);
    }
  }, []);

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
          onResetState={resetState}
        />
      </div>

      {status && (
        <div className="status-message">
          {isLoading && <span className="loading"></span>}
          {status}
        </div>
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

