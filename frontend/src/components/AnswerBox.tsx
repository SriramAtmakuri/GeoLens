import { useState } from 'react';
import type { TraceInfo, QueryStats } from '../api/types';

interface Props {
  answer: string;
  stats: QueryStats;
  trace: TraceInfo;
  hydeUsed: boolean;
  queryVariations: string[];
}

// Parses [filename.txt] and (filename.txt) citation patterns into numbered refs.
function parseAnswer(text: string): { nodes: React.ReactNode[]; refs: string[] } {
  const pattern = /(\[[^\]]+\.(?:txt|pdf)\]|\([^)]+\.(?:txt|pdf)\))/g;
  const refs: string[] = [];
  const refMap = new Map<string, number>();

  let m: RegExpExecArray | null;
  while ((m = pattern.exec(text)) !== null) {
    const raw = m[1].replace(/^[\[(]|[\])]$/g, '');
    if (!refMap.has(raw)) { refMap.set(raw, refs.length + 1); refs.push(raw); }
  }

  if (refs.length === 0) return { nodes: [text], refs: [] };

  const parts = text.split(/(\[[^\]]+\.(?:txt|pdf)\]|\([^)]+\.(?:txt|pdf)\))/g);
  const nodes: React.ReactNode[] = parts.map((part, i) => {
    const inner = part.replace(/^[\[(]|[\])]$/g, '');
    const num = refMap.get(inner);
    if (num !== undefined) {
      return <sup key={i} className="cite-sup" title={inner}>[{num}]</sup>;
    }
    return part || null;
  });

  return { nodes, refs };
}

export default function AnswerBox({ answer, stats, trace, hydeUsed, queryVariations }: Props) {
  const [copied, setCopied] = useState(false);
  const total = trace.total_ms || 1;
  const segments = [
    { label: 'Embed',  ms: trace.embedding_ms,    color: '#6366f1' },
    { label: 'Query',  ms: trace.hybrid_query_ms,  color: '#22c55e' },
    { label: 'Rerank', ms: trace.reranking_ms,     color: '#f59e0b' },
    { label: 'LLM',    ms: trace.llm_synthesis_ms, color: '#ec4899' },
  ];

  const copy = () => {
    navigator.clipboard.writeText(answer).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  const { nodes, refs } = parseAnswer(answer);

  return (
    <div className="answer-box">
      <div className="answer-header">
        <span className="answer-label">Answer</span>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <span className="answer-stats">
            {stats.chunks_returned}/{stats.chunks_in_polygon} chunks · {total}ms
          </span>
          <button className={`copy-btn${copied ? ' copied' : ''}`} onClick={copy}>
            {copied ? '✓ Copied' : 'Copy'}
          </button>
        </div>
      </div>

      <div className="pipeline-badges">
        {hydeUsed && <span className="badge-pill hyde">HyDE</span>}
        {queryVariations.length > 1 && (
          <span className="badge-pill expand" title={queryVariations.slice(1).join('\n')}>
            {queryVariations.length} variations
          </span>
        )}
      </div>

      <p className="answer-text">{nodes}</p>

      {refs.length > 0 && (
        <div className="cite-footnotes">
          {refs.map((ref, i) => (
            <div key={ref} className="cite-footnote">
              <span className="cite-num">[{i + 1}]</span>
              <span className="cite-ref">{ref.replace(/\.(?:txt|pdf)$/, '')}</span>
            </div>
          ))}
        </div>
      )}

      <div className="trace-bar" title="Latency breakdown">
        {segments.map(s => (
          <div
            key={s.label}
            style={{
              width: `${(s.ms / total) * 100}%`,
              background: s.color,
              height: '5px',
              minWidth: s.ms > 0 ? 2 : 0,
            }}
            title={`${s.label}: ${s.ms}ms`}
          />
        ))}
      </div>
      <div className="trace-legend">
        {segments.map(s => (
          <span key={s.label} className="trace-seg">
            <span className="trace-dot" style={{ background: s.color }} />
            {s.label} {s.ms}ms
          </span>
        ))}
      </div>
    </div>
  );
}
