import { useState, useEffect } from 'react';
import { api } from '../api/client';
import type { EvalRunResponse } from '../api/types';

interface EvalQuery { id: string; question: string; created_at: string; }

export default function EvalTab() {
  const [running, setRunning]       = useState(false);
  const [result, setResult]         = useState<EvalRunResponse | null>(null);
  const [error, setError]           = useState<string | null>(null);
  const [evalQueries, setEvalQueries] = useState<EvalQuery[]>([]);

  useEffect(() => {
    api.listEvalQueries().then(qs => setEvalQueries(qs as EvalQuery[])).catch(() => {});
  }, []);

  const runEval = async () => {
    setRunning(true);
    setError(null);
    try {
      setResult(await api.runEval());
    } catch (e: any) {
      setError(e.message);
    } finally {
      setRunning(false);
    }
  };

  const hitRate    = result ? `${(result.hit_rate * 100).toFixed(1)}%` : '—';
  const mrr        = result ? result.mrr.toFixed(3) : '—';
  const queryCount = result ? result.results.length : (evalQueries.length || '—');

  return (
    <div className="eval-tab">

      <div className="eval-header-card">
        <h3>Retrieval Evaluation</h3>
        <p>
          Runs all saved eval queries against the live pipeline and reports
          Hit Rate and MRR against pre-built ground truth for the NYC dataset.
          Load sample data first if no queries appear below.
        </p>
        <button className="eval-btn" onClick={runEval} disabled={running}>
          {running ? 'Running evaluation…' : 'Run Evaluation'}
        </button>
      </div>

      {error && <div className="error-box">{error}</div>}

      <div className="eval-metrics">
        <div className="metric-card">
          <span className="metric-val">{hitRate}</span>
          <span className="metric-label">Hit Rate</span>
        </div>
        <div className="metric-card">
          <span className="metric-val">{mrr}</span>
          <span className="metric-label">MRR</span>
        </div>
        <div className="metric-card">
          <span className="metric-val">{queryCount}</span>
          <span className="metric-label">Queries</span>
        </div>
      </div>

      {result ? (
        <table className="eval-table">
          <thead>
            <tr>
              <th>Question</th>
              <th>Hit</th>
              <th>Rank</th>
            </tr>
          </thead>
          <tbody>
            {result.results.map((r, i) => (
              <tr key={i}>
                <td>{r.question}</td>
                <td>
                  <span className={`badge ${r.hit ? 'hit' : 'miss'}`}>
                    {r.hit ? 'HIT' : 'MISS'}
                  </span>
                </td>
                <td>{r.rank_of_first_hit ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : evalQueries.length > 0 ? (
        <div className="eval-queries-preview">
          <p className="eval-queries-label">Ground-truth queries ({evalQueries.length})</p>
          <table className="eval-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Question</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {evalQueries.map((q, i) => (
                <tr key={q.id}>
                  <td style={{ color: 'var(--text-3)', width: 32 }}>{i + 1}</td>
                  <td>{q.question}</td>
                  <td><span className="badge-ready">ready</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="empty-hint">No eval queries found — load the NYC sample data first.</p>
      )}

    </div>
  );
}
