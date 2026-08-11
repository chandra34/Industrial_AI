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
          <div className="agent-system-badge">
            <span className="agent-badge-icon">⚡</span>
            <span>Industrial AI Multi-Agent System</span>
          </div>

          <h1 className="agent-welcome-title">Plant Operations Intelligence</h1>
          <p className="agent-welcome-desc">
            Query real-time OPC UA machine telemetry, SAP ERP inventory, and OEM technical manuals.
          </p>

          <div className="agent-cards-grid">
            <div className="agent-capability-card">
              <div className="agent-card-icon">📦</div>
              <h3 className="agent-card-title">SAP Spare Parts Inventory</h3>
              <p className="agent-card-desc">Query material master data, stock availability, and warehouse locations.</p>
            </div>

            <div className="agent-capability-card">
              <div className="agent-card-icon">⚡</div>
              <h3 className="agent-card-title">Live Machine Sensors</h3>
              <p className="agent-card-desc">Inspect real-time PLC telemetry, vibration, temperature, and alarm logs.</p>
            </div>

            <div className="agent-capability-card">
              <div className="agent-card-icon">🔧</div>
              <h3 className="agent-card-title">SAP Plant Maintenance</h3>
              <p className="agent-card-desc">View active maintenance work orders, equipment history, and inspection lots.</p>
            </div>

            <div className="agent-capability-card">
              <div className="agent-card-icon">🛡️</div>
              <h3 className="agent-card-title">OEM Manuals &amp; PTW Compliance</h3>
              <p className="agent-card-desc">Search technical manuals, torque limits, and audit Permit-to-Work safety rules.</p>
            </div>
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
