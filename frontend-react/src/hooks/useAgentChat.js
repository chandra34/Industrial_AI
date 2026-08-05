import { useState, useCallback } from 'react';
import { queryAgent } from '../api/client';

/**
 * Custom React hook to manage industrial multi-agent conversation state and orchestrator queries.
 *
 * @returns {Object} Agent chat state, message history, loader status, and dispatch methods.
 */
export function useAgentChat() {
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [maxSteps, setMaxSteps] = useState(10);

  /**
   * Dispatches user prompts to the multi-agent orchestrator endpoint,
   * measures execution timing, and appends agent responses with tool call records.
   *
   * @async
   * @param {string} question - The user's input prompt.
   */
  const handleSend = useCallback(async (question) => {
    if (!question.trim()) return;

    const userMessage = {
      role: 'user',
      content: question,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);

    const startTime = Date.now();
    try {
      const response = await queryAgent(question, 'operator', null, maxSteps);
      const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);

      const botMessage = {
        role: 'assistant',
        content: response.answer,
        toolCalls: response.tool_calls || [],
        stepsTaken: response.steps_taken,
        llmProvider: response.llm_provider_used,
        llmModel: response.llm_model_used,
        totalTime: elapsed,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, botMessage]);
    } catch (err) {
      const botMessage = {
        role: 'assistant',
        content: `Error: ${err.message}`,
        toolCalls: [],
        stepsTaken: 0,
        totalTime: ((Date.now() - startTime) / 1000).toFixed(1),
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, botMessage]);
    } finally {
      setIsLoading(false);
    }
  }, [maxSteps]);

  /**
   * Resets active conversation history state and pending indicators.
   */
  const clearMessages = useCallback(() => {
    setMessages([]);
    setIsLoading(false);
  }, []);

  return {
    messages,
    isLoading,
    maxSteps,
    setMaxSteps,
    handleSend,
    clearMessages,
  };
}
