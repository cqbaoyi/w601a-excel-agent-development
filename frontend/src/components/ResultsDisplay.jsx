import React from 'react';

/**
 * Component to display execution results
 */
export default function ResultsDisplay({ output, error, success }) {
  if (!output && !error) {
    return null;
  }

  return (
    <div className="result-card">
      <h3>Execution Results</h3>
      {error && (
        <div className="error-display">
          <strong>Error:</strong>
          <br />
          {error}
        </div>
      )}
      {output && (
        <div className="output-display">{output}</div>
      )}
    </div>
  );
}

