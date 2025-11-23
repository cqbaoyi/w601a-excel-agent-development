import React from 'react';

/**
 * Component to display column traceability information
 */
export default function ColumnTraceability({ columns, originalFile }) {
  if (!columns || columns.length === 0) {
    return null;
  }

  return (
    <div className="column-traceability">
      <h3>Data Column Traceability</h3>
      {originalFile && (
        <p style={{ marginBottom: '15px', color: '#666', fontSize: '14px' }}>
          Source file: <strong>{originalFile}</strong>
        </p>
      )}
      <ul className="column-list">
        {columns.map((column, index) => (
          <li key={index}>{column}</li>
        ))}
      </ul>
    </div>
  );
}

