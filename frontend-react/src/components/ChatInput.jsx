import { useState } from 'react';
import './ChatInput.css';

/**
 * ChatInput component containing a textarea and action buttons for sending queries and launching the upload modal.
 * Supports submitting messages on Enter (without Shift) and auto-resets text after submission.
 *
 * @component
 * @param {Object} props - Component props.
 * @param {function(string): void} props.onSend - Callback invoked when a query is successfully submitted.
 * @param {function(): void} props.onUploadClick - Callback to open the PDF upload modal window.
 * @param {boolean} props.disabled - If true, disables input textarea and action buttons.
 * @returns {React.JSX.Element} The rendered message input form.
 */
export default function ChatInput({ onSend, onUploadClick, disabled }) {
  const [text, setText] = useState('');

  /**
   * Submits user input text, prevents default form action, resets form state.
   *
   * @param {React.FormEvent} e - Form submission event.
   */
  function handleSubmit(e) {
    e.preventDefault();
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setText('');
  }

  /**
   * Keyboard handler to submit the form when Enter is pressed without the Shift modifier.
   *
   * @param {React.KeyboardEvent} e - Keyboard event.
   */
  function handleKeyDown(e) {

    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  }

  return (
    <div className="chat-input-wrapper">
      <form className="chat-input-form" onSubmit={handleSubmit}>
        <textarea
          className="chat-input-textarea"
          placeholder="Ask about live sensors, SAP inventory, or OEM SOPs..."
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={1}
          disabled={disabled}
        />
        <div className="chat-input-actions">
          <div className="chat-input-left-actions">
            <button type="button" className="chat-input-icon-btn" onClick={onUploadClick} title="Upload PDF">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
              </svg>
            </button>
          </div>
          <button
            type="submit"
            className="chat-input-send-btn"
            disabled={!text.trim() || disabled}
            title="Send"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          </button>
        </div>
      </form>
      <p className="chat-input-hint">Press Enter to send · Shift + Enter for new line</p>
    </div>
  );
}
