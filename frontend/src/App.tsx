import { useState } from 'react';
import MapView from './components/Map';
import QueryPanel from './components/QueryPanel';
import IngestionPanel from './components/IngestionPanel';
import EvalTab from './components/EvalTab';
import type { GeoJSONPolygon, ChunkResult } from './api/types';

type Tab = 'query' | 'documents' | 'eval';

export default function App() {
  const [polygon, setPolygon] = useState<GeoJSONPolygon | null>(null);
  const [chunks, setChunks] = useState<ChunkResult[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>('query');
  const [isSearching, setIsSearching] = useState(false);

  return (
    <div className="app">
      <header className="app-header">
        <h1 className="logo">GeoLens</h1>
        <nav className="tabs" style={{ marginLeft: 'auto' }}>
          <button className={tab === 'query' ? 'active' : ''} onClick={() => setTab('query')}>Query</button>
          <button className={tab === 'documents' ? 'active' : ''} onClick={() => setTab('documents')}>Documents</button>
          <button className={tab === 'eval' ? 'active' : ''} onClick={() => setTab('eval')}>Evaluate</button>
        </nav>
      </header>

      {tab === 'query' && (
        <div className="main-layout">
          <div className="map-pane">
            <MapView
              onPolygonDrawn={setPolygon}
              onPolygonCleared={() => { setPolygon(null); setChunks([]); setSelectedId(null); }}
              chunks={chunks}
              selectedChunkId={selectedId}
              onChunkSelect={id => setSelectedId(id)}
              isLoading={isSearching}
            />
          </div>
          <div className="panel-pane">
            <QueryPanel
              polygon={polygon}
              selectedChunkId={selectedId}
              onChunkSelect={id => setSelectedId(id)}
              onResults={c => { setChunks(c); setSelectedId(null); }}
              onLoadingChange={setIsSearching}
            />
          </div>
        </div>
      )}

      {tab === 'documents' && (
        <div className="full-pane">
          <IngestionPanel onDocumentsChange={() => {}} />
        </div>
      )}

      {tab === 'eval' && (
        <div className="full-pane">
          <EvalTab />
        </div>
      )}
    </div>
  );
}
