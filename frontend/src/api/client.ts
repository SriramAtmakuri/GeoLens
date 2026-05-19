import type {
  QueryRequest, QueryResponse, Document, JobStatus, EvalRunResponse,
} from './types';

const BASE = '/api';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  query: (body: QueryRequest) =>
    request<QueryResponse>('/query', { method: 'POST', body: JSON.stringify(body) }),

  listDocuments: () => request<Document[]>('/documents'),

  deleteDocument: (id: string) =>
    fetch(`${BASE}/documents/${id}`, { method: 'DELETE' }).then(r => {
      if (!r.ok) throw new Error(`${r.status}`);
    }),

  loadSampleData: () =>
    request<{ documents_loaded: number; chunks_loaded: number; message: string }>(
      '/sample-data',
      { method: 'POST' },
    ),

  ingestFile: (file: File, lat: number, lng: number, title: string) => {
    const fd = new FormData();
    fd.append('file', file);
    fd.append('lat', String(lat));
    fd.append('lng', String(lng));
    fd.append('title', title);
    return fetch(`${BASE}/ingest`, { method: 'POST', body: fd }).then(r => {
      if (!r.ok) return r.text().then(t => { throw new Error(`${r.status}: ${t}`); });
      return r.json();
    });
  },

  getJob: (jobId: string) => request<JobStatus>(`/ingest/jobs/${jobId}`),

  listJobs: () => request<JobStatus[]>('/ingest/jobs'),

  runEval: () => request<EvalRunResponse>('/eval/run', { method: 'POST' }),

  listEvalQueries: () =>
    request<Array<{ id: string; question: string; created_at: string }>>(
      '/eval/queries',
    ),
};
