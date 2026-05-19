import { useState } from 'react';
import type { ChunkResult } from '../api/types';

interface Props {
  chunk: ChunkResult;
  selected: boolean;
  onClick: () => void;
}

export default function ResultCard({ chunk, selected, onClick }: Props) {
  const [expanded, setExpanded] = useState(false);
  const score = chunk.hybrid_score;
  const pct = Math.min(Math.round(score * 100), 100);

  return (
    <div
      className={`result-card ${selected ? 'selected' : ''}`}
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={e => e.key === 'Enter' && onClick()}
    >
      <div className="result-meta">
        <span className="result-source">{chunk.source || 'Unknown'}</span>
        <span className="result-rank">#{chunk.final_rank}</span>
      </div>

      <p className="result-snippet">
        {expanded ? chunk.content : chunk.content.slice(0, 200) + (chunk.content.length > 200 ? '…' : '')}
      </p>

      {expanded && (
        <div className="result-scores">
          <span title="Vector similarity">V {chunk.vector_score.toFixed(3)}</span>
          <span title="BM25 text rank">T {chunk.bm25_score.toFixed(3)}</span>
          {chunk.rerank_score != null && (
            <span title="Cross-encoder rerank score">R {chunk.rerank_score.toFixed(3)}</span>
          )}
        </div>
      )}

      {chunk.content.length > 200 && (
        <button
          className="expand-btn"
          onClick={e => { e.stopPropagation(); setExpanded(x => !x); }}
        >
          {expanded ? '▲ Show less' : '▼ Show more'}
        </button>
      )}

      <div className="score-row">
        <div className="score-bar-wrap">
          <div className="score-bar" style={{ width: `${pct}%` }} />
        </div>
        <span className="score-label">{score.toFixed(3)}</span>
      </div>

      <button
        className="view-map-btn"
        onClick={e => { e.stopPropagation(); onClick(); }}
      >
        View on map
      </button>
    </div>
  );
}
