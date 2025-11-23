import React, { useState } from 'react';

/**
 * Text input component for questions
 */
export default function TextInput({ onAnalyze, disabled }) {
  const [question, setQuestion] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (question.trim() && !disabled) {
      onAnalyze(question.trim());
      setQuestion('');
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <div className="input-group">
        <label htmlFor="question">Enter your question (Chinese or English):</label>
        <input
          id="question"
          type="text"
          className="text-input"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="e.g., Analyze sales trends in different regions"
          disabled={disabled}
        />
      </div>
      <div className="button-group">
        <button
          type="submit"
          className="btn btn-primary"
          disabled={!question.trim() || disabled}
        >
          Analyze
        </button>
      </div>
    </form>
  );
}

