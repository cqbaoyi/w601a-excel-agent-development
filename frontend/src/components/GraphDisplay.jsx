import React from 'react';

/**
 * Component to display generated graph HTML files
 */
export default function GraphDisplay({ graphFiles }) {
  if (!graphFiles || graphFiles.length === 0) {
    return null;
  }

  const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

  return (
    <div className="graph-display">
      <h3>Generated Graphs</h3>
      {graphFiles.map((filename, index) => (
        <div key={index} className="graph-container">
          <div className="graph-header">
            <h4>{filename}</h4>
            <a
              href={`${API_BASE_URL}/output/${encodeURIComponent(filename)}`}
              target="_blank"
              rel="noopener noreferrer"
              className="graph-link"
            >
              Open in new tab
            </a>
          </div>
          <iframe
            src={`${API_BASE_URL}/output/${encodeURIComponent(filename)}`}
            title={filename}
            className="graph-iframe"
            sandbox="allow-scripts allow-same-origin"
          />
        </div>
      ))}
    </div>
  );
}

