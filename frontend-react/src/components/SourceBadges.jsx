import './SourceBadges.css';

/**
 * SourceBadges component rendering a list of numbered badges corresponding to query references.
 * Clicking a badge reveals detailed context (chunks, page numbers, confidence score).
 *
 * @component
 * @param {Object} props - Component props.
 * @param {Array<{source_filename: string, page_number: number, chunk_text: string, score: number}>} props.sources - Array of context citation metadata.
 * @param {function(any): void} props.onSourceClick - Callback invoked when a badge is selected/expanded.
 * @returns {React.JSX.Element|null} The list of badge buttons or null if no sources are passed.
 */
export default function SourceBadges({ sources, onSourceClick }) {

  if (!sources || sources.length === 0) return null;

  return (
    <div className="source-badges">
      {sources.map((source, index) => (
        <button
          key={index}
          className="source-badge"
          onClick={() => onSourceClick?.(source)}
          title={`${source.source_filename} — page ${source.page_number}`}
        >
          {index + 1}
        </button>
      ))}
    </div>
  );
}
