import { useState } from 'react';
import type { GeoJSONPolygon, QueryResponse, ChunkResult } from '../api/types';
import { api } from '../api/client';
import AnswerBox from './AnswerBox';
import ResultCard from './ResultCard';

const SUGGESTED = [
  'What are the height limits for residential buildings?',
  'What affordable housing requirements apply here?',
  'Which zoning districts allow mixed-use development?',
  'What are the parking requirements for commercial buildings?',
];

interface Props {
  polygon: GeoJSONPolygon | null;
  selectedChunkId: string | null;
  onChunkSelect: (id: string) => void;
  onResults: (chunks: ChunkResult[]) => void;
  onLoadingChange: (loading: boolean) => void;
}

export default function QueryPanel({ polygon, selectedChunkId, onChunkSelect, onResults, onLoadingChange }: Props) {
  const [question, setQuestion] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<QueryResponse | null>(null);
  const [vectorWeight, setVectorWeight] = useState(0.4);
  const bm25Weight = +(1 - vectorWeight).toFixed(2);

  const handleQuery = async () => {
    if (!polygon || !question.trim()) return;
    setLoading(true);
    onLoadingChange(true);
    setError(null);
    try {
      const res = await api.query({
        question,
        polygon,
        top_k: 8,
        similarity_threshold: 0.0,
        vector_weight: vectorWeight,
        bm25_weight: bm25Weight,
      });
      setResult(res);
      onResults(res.chunks);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
      onLoadingChange(false);
    }
  };

  return (
    <div className="query-panel">
      <div className="query-input-area">
        <textarea
          className="question-input"
          placeholder="Ask a question about the selected area…"
          value={question}
          onChange={e => setQuestion(e.target.value)}
          rows={3}
          onKeyDown={e => {
            if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleQuery();
          }}
        />
        <div className="kbd-hint"><kbd>⌘</kbd> + <kbd>↵</kbd> to search</div>

        <div className="weight-slider">
          <label>Vector {vectorWeight.toFixed(2)} / BM25 {bm25Weight.toFixed(2)}</label>
          <input
            type="range" min={0} max={1} step={0.05}
            value={vectorWeight}
            onChange={e => setVectorWeight(+e.target.value)}
          />
        </div>

        <button
          className="submit-btn"
          onClick={handleQuery}
          disabled={!polygon || !question.trim() || loading}
        >
          {loading ? 'Searching…' : polygon ? 'Search Area' : 'Draw a polygon first'}
        </button>
      </div>

      {error && <div className="error-box">{error}</div>}

      {polygon && !result && !loading && (
        <div className="suggested-queries">
          <span className="suggested-label">Try asking</span>
          <div className="suggested-list">
            {SUGGESTED.map(q => (
              <button key={q} className="suggested-btn" onClick={() => setQuestion(q)}>
                {q}
              </button>
            ))}
          </div>
        </div>
      )}

      {!polygon && (
        <div className="hint-box">
          Draw a polygon on the map to define the search area, then type your question.
        </div>
      )}

      {result && (
        <div className="results-area">
          <div className="results-divider" />
          <AnswerBox
            answer={result.answer}
            stats={result.query_stats}
            trace={result.trace}
            hydeUsed={result.hyde_used}
            queryVariations={result.query_variations}
          />
          <p className="sources-label">Sources ({result.chunks.length})</p>
          <div className="chunks-list">
            {result.chunks.map(chunk => (
              <ResultCard
                key={chunk.id}
                chunk={chunk}
                selected={chunk.id === selectedChunkId}
                onClick={() => onChunkSelect(chunk.id)}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
