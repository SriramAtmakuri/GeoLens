import { useState, useEffect, useRef } from 'react';
import { api } from '../api/client';
import type { Document, JobStatus } from '../api/types';

interface Props {
  onDocumentsChange: () => void;
}

export default function IngestionPanel({ onDocumentsChange }: Props) {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [lat, setLat] = useState('40.7549');
  const [lng, setLng] = useState('-73.9857');
  const [title, setTitle] = useState('');
  const [uploading, setUploading] = useState(false);
  const [activeJob, setActiveJob] = useState<JobStatus | null>(null);
  const [sampleLoading, setSampleLoading] = useState(false);
  const [sampleMsg, setSampleMsg] = useState('');
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadDocs = async () => {
    const docs = await api.listDocuments();
    setDocuments(docs);
    onDocumentsChange();
  };

  useEffect(() => {
    loadDocs();
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  const pollJob = (jobId: string) => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      const job = await api.getJob(jobId);
      setActiveJob(job);
      if (job.status === 'completed' || job.status === 'failed') {
        clearInterval(pollRef.current!);
        pollRef.current = null;
        setUploading(false);
        loadDocs();
      }
    }, 2000);
  };

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    setActiveJob(null);
    try {
      const res = await api.ingestFile(file, parseFloat(lat), parseFloat(lng), title || file.name);
      setActiveJob({ job_id: res.job_id, status: 'pending', filename: file.name, total_chunks: null, processed_chunks: 0, progress: 0, error_message: null, started_at: new Date().toISOString(), completed_at: null });
      pollJob(res.job_id);
    } catch (e: any) {
      setActiveJob({ job_id: '', status: 'failed', filename: file.name, total_chunks: null, processed_chunks: 0, progress: 0, error_message: e.message, started_at: new Date().toISOString(), completed_at: null });
      setUploading(false);
    }
  };

  const handleLoadSample = async () => {
    setSampleLoading(true);
    setSampleMsg('');
    try {
      const res = await api.loadSampleData();
      setSampleMsg(res.message);
      loadDocs();
    } catch (e: any) {
      setSampleMsg(`Error: ${e.message}`);
    } finally {
      setSampleLoading(false);
    }
  };

  const handleDelete = async (id: string) => {
    await api.deleteDocument(id);
    loadDocs();
  };

  return (
    <div className="ingest-panel">
      <div className="sample-section">
        <h3>NYC Sample Dataset</h3>
        <p>25 pre-built chunks from NYC zoning/permit data spread across all 5 boroughs.</p>
        <button className="sample-btn" onClick={handleLoadSample} disabled={sampleLoading}>
          {sampleLoading ? 'Loading…' : 'Load NYC Sample Data'}
        </button>
        {sampleMsg && <div className="sample-msg">{sampleMsg}</div>}
      </div>

      <div className="upload-section">
        <h3>Upload Document</h3>
        <label
          className={`drop-zone${file ? ' has-file' : ''}`}
          onDragOver={e => { e.preventDefault(); e.currentTarget.classList.add('drag-over'); }}
          onDragLeave={e => e.currentTarget.classList.remove('drag-over')}
          onDrop={e => {
            e.preventDefault();
            e.currentTarget.classList.remove('drag-over');
            const f = e.dataTransfer.files[0];
            if (f) setFile(f);
          }}
        >
          <input type="file" accept=".pdf,.txt" onChange={e => setFile(e.target.files?.[0] || null)} />
          {file ? `📄 ${file.name}` : 'Drag & drop PDF or TXT here, or click to browse'}
        </label>
        <div className="coord-row">
          <label>Lat <input value={lat} onChange={e => setLat(e.target.value)} /></label>
          <label>Lng <input value={lng} onChange={e => setLng(e.target.value)} /></label>
        </div>
        <input
          placeholder="Document title (optional)"
          value={title}
          onChange={e => setTitle(e.target.value)}
        />
        <button onClick={handleUpload} disabled={!file || uploading}>
          {uploading ? 'Uploading…' : file ? 'Upload & Ingest' : 'Select a file first'}
        </button>
      </div>

      {activeJob && (
        <div className="job-progress">
          <div className="job-status">
            Job {activeJob.status} — {activeJob.filename}
          </div>
          <div className="progress-bar-wrap">
            <div
              className="progress-bar-fill"
              style={{ width: `${Math.round(activeJob.progress * 100)}%` }}
            />
          </div>
          <div className="progress-text">
            {activeJob.processed_chunks}/{activeJob.total_chunks ?? '?'} chunks
            ({Math.round(activeJob.progress * 100)}%)
          </div>
          {activeJob.error_message && (
            <div className="error-box">{activeJob.error_message}</div>
          )}
        </div>
      )}

      <div className="doc-list">
        <h3>Ingested Documents ({documents.length})</h3>
        {documents.length === 0 && <p className="empty-hint">No documents yet. Load sample data or upload a file.</p>}
        {documents.map(doc => (
          <div key={doc.id} className="doc-row">
            <div>
              <strong>{doc.title}</strong>
              <span className="doc-meta"> · {doc.chunk_count} chunks · {doc.source}</span>
            </div>
            <button className="del-btn" onClick={() => handleDelete(doc.id)} title="Delete document">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="3 6 5 6 21 6"/>
                <path d="M19 6l-1 14H6L5 6"/>
                <path d="M10 11v6M14 11v6"/>
                <path d="M9 6V4h6v2"/>
              </svg>
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
