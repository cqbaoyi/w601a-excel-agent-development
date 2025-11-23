import React from 'react';

/**
 * Component to display generated Python code
 */
export default function CodeDisplay({ code }) {
  if (!code) {
    return null;
  }

  return (
    <div className="result-card">
      <h3>Generated Python Code</h3>
      <div className="code-display">{code}</div>
    </div>
  );
}

