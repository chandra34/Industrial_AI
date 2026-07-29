import { useRef, useEffect } from 'react';
import AgentMessage from './AgentMessage';
import ChatInput from './ChatInput';
import './AgentChatArea.css';

/**
 * AgentChatArea component representing the Industrial AI Agent canvas workspace.
 * Renders hero welcome header, interactive quick-prompt suggestion chips,
 * conversation message list, reasoning state indicators, and the chat input form.
 *
 * @component
 * @param {Object} props - Component props.
 * @param {Array<Object>} props.messages - List of agent chat message objects.
 * @param {boolean} props.isLoading - If true, displays agent reasoning loader state.
 * @param {function(string): void} props.onSend - Submit callback for new prompts.
 * @returns {React.JSX.Element} Rendered agent workspace window.
 */
export default function AgentChatArea({ messages, isLoading, onSend }) {
  const scrollRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isLoading]);

  return (
    <div className="agent-chat-area">
      <div className="agent-chat-scroll" ref={scrollRef}>
        {/* Welcome Header */}
        <div className="agent-welcome">
          <h1 className="agent-welcome-title">Industrial AI Agent 🤖</h1>
          <h2 className="agent-welcome-subtitle">Ask anything about plant operations</h2>
          <p className="agent-welcome-desc">
            I'll query SAP ERP (stock, work orders), OPC UA sensors, and technical manuals to give you ground-truth answers.
          </p>

          <div className="agent-welcome-chips">
            <button
              type="button"
              className="agent-chip"
              onClick={() => onSend('Check stock for bearing SKF-6214 in plant 1010')}
            >
              📦 Check bearing stock
            </button>
            <button
              type="button"
              className="agent-chip"
              onClick={() => onSend('Show active work orders for plant 1010')}
            >
              🔧 Active work orders
            </button>
            <button
              type="button"
              className="agent-chip"
              onClick={() => onSend('Search technical manuals for equipment maintenance safety guidelines')}
            >
              📖 Maintenance safety SOP
            </button>
          </div>
        </div>

        {/* Message Thread */}
        <div className="agent-messages">
          {messages.map((msg, index) => (
            <AgentMessage
              key={msg.id || `${msg.role}-${new Date(msg.timestamp).getTime()}-${index}`}
              message={msg}
            />
          ))}

          {isLoading && (
            <div className="agent-loading">
              <div className="agent-loading-dots">
                <span></span><span></span><span></span>
              </div>
              <p>Agent is reasoning and executing tools across SAP and Vector RAG...</p>
            </div>
          )}
        </div>
      </div>

      <ChatInput onSend={onSend} onUploadClick={() => {}} disabled={isLoading} />
    </div>
  );
}
