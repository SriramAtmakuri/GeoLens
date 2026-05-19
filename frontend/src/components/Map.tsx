import { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import type { ChunkResult, GeoJSONPolygon } from '../api/types';

interface Props {
  onPolygonDrawn: (polygon: GeoJSONPolygon) => void;
  onPolygonCleared: () => void;
  chunks: ChunkResult[];
  selectedChunkId: string | null;
  onChunkSelect: (id: string) => void;
  isLoading: boolean;
}

const pinIcon = (active: boolean) =>
  L.divIcon({
    className: '',
    html: `<div style="
      width:${active ? 20 : 14}px;
      height:${active ? 20 : 14}px;
      border-radius:50%;
      background:${active ? '#f97316' : '#3b82f6'};
      border:2px solid white;
      box-shadow:0 1px 4px rgba(0,0,0,.4);
      transition:all .15s;
    "></div>`,
    iconSize: [active ? 20 : 14, active ? 20 : 14],
    iconAnchor: [active ? 10 : 7, active ? 10 : 7],
  });

const STREET = 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png';
const SATELLITE = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}';

export default function MapView({ onPolygonDrawn, onPolygonCleared, chunks, selectedChunkId, onChunkSelect, isLoading }: Props) {
  const mapRef = useRef<L.Map | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const markersRef = useRef<Map<string, L.Marker>>(new Map());
  const drawnLayersRef = useRef<L.FeatureGroup | null>(null);
  const tileLayerRef = useRef<L.TileLayer | null>(null);
  const [satellite, setSatellite] = useState(false);
  const [hasPolygon, setHasPolygon] = useState(false);

  useEffect(() => {
    if (mapRef.current || !containerRef.current) return;
    let map: L.Map;
    let destroyed = false;

    (async () => {
      (window as any).L = L;
      await import('leaflet-draw');
      if (destroyed || !containerRef.current) return;

      map = L.map(containerRef.current, { center: [40.73, -73.93], zoom: 11 });
      const tile = L.tileLayer(STREET, {
        attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors © <a href="https://carto.com/attributions">CARTO</a>',
        subdomains: 'abcd',
        maxZoom: 20,
      }).addTo(map);
      tileLayerRef.current = tile;

      const drawnItems = new L.FeatureGroup();
      map.addLayer(drawnItems);
      drawnLayersRef.current = drawnItems;

      const drawControl = new (L as any).Control.Draw({
        edit: { featureGroup: drawnItems },
        draw: {
          polygon: { allowIntersection: false, showArea: true },
          polyline: false,
          rectangle: true,
          circle: false,
          circlemarker: false,
          marker: false,
        },
      });
      map.addControl(drawControl);

      map.on((L as any).Draw.Event.CREATED, (e: any) => {
        drawnItems.clearLayers();
        drawnItems.addLayer(e.layer);
        setHasPolygon(true);
        onPolygonDrawnRef.current(e.layer.toGeoJSON().geometry as GeoJSONPolygon);
      });

      map.on((L as any).Draw.Event.EDITED, () => {
        drawnItems.eachLayer((layer: any) => {
          onPolygonDrawnRef.current(layer.toGeoJSON().geometry as GeoJSONPolygon);
        });
      });

      map.on((L as any).Draw.Event.DELETED, () => {
        if (drawnItems.getLayers().length === 0) {
          setHasPolygon(false);
          onPolygonClearedRef.current();
        }
      });

      mapRef.current = map;
    })();

    return () => {
      destroyed = true;
      if (mapRef.current) { mapRef.current.remove(); mapRef.current = null; }
    };
  }, []);

  const onPolygonDrawnRef = useRef(onPolygonDrawn);
  useEffect(() => { onPolygonDrawnRef.current = onPolygonDrawn; }, [onPolygonDrawn]);

  const onPolygonClearedRef = useRef(onPolygonCleared);
  useEffect(() => { onPolygonClearedRef.current = onPolygonCleared; }, [onPolygonCleared]);

  useEffect(() => {
    if (!tileLayerRef.current) return;
    tileLayerRef.current.setUrl(satellite ? SATELLITE : STREET);
  }, [satellite]);

  const clearPolygon = () => {
    drawnLayersRef.current?.clearLayers();
    setHasPolygon(false);
    onPolygonClearedRef.current();
  };

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    markersRef.current.forEach(m => m.remove());
    markersRef.current.clear();

    chunks.forEach(chunk => {
      if (!chunk.location?.coordinates) return;
      const [lng, lat] = chunk.location.coordinates;
      const marker = L.marker([lat, lng], { icon: pinIcon(chunk.id === selectedChunkId) }).addTo(map);
      marker.bindPopup(
        `<b>${chunk.source || 'Unknown'}</b><br>${chunk.content.slice(0, 100)}…<br>` +
        `<small>score: ${chunk.hybrid_score.toFixed(3)}</small>`,
      );
      marker.on('click', () => onChunkSelect(chunk.id));
      markersRef.current.set(chunk.id, marker);
    });

    if (chunks.length > 0) {
      const points = chunks.filter(c => c.location?.coordinates)
        .map(c => L.latLng(c.location.coordinates[1], c.location.coordinates[0]));
      if (points.length) map.fitBounds(L.latLngBounds(points).pad(0.3));
    }
  }, [chunks]);

  useEffect(() => {
    markersRef.current.forEach((marker, id) => marker.setIcon(pinIcon(id === selectedChunkId)));
    if (selectedChunkId) {
      const m = markersRef.current.get(selectedChunkId);
      if (m) m.openPopup();
    }
  }, [selectedChunkId]);

  return (
    <div style={{ width: '100%', height: '100%', position: 'relative' }}>
      <div ref={containerRef} style={{ width: '100%', height: '100%', minHeight: 400 }} />

      <div className="map-overlays">
        <button className="map-overlay-btn" onClick={() => setSatellite(s => !s)} title="Toggle satellite/street">
          {satellite ? '🗺️' : '🛰️'}
        </button>
      </div>

      {hasPolygon && (
        <div className="map-clear-area">
          <button className="map-overlay-btn map-clear-btn" onClick={clearPolygon} title="Clear drawn area">
            ✕ Clear area
          </button>
        </div>
      )}

      {!hasPolygon && !isLoading && (
        <div className="map-onboarding">
          <div className="map-onboarding-inner">
            <span className="map-onboarding-icon">⬡</span>
            <span>Draw a polygon or rectangle to define your search area</span>
          </div>
        </div>
      )}

      {isLoading && (
        <div className="map-loading-overlay">
          <div className="map-spinner" />
        </div>
      )}
    </div>
  );
}
