import './SourceBadges.css';

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
