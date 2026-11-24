import React, { useEffect, useRef, useState } from 'react';
import maplibregl, { type Map as MapLibreMap, type Marker } from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';

export type VexaMapDriver = {
  user_id: string;
  username: string;
  phone?: string | null;
  is_online: boolean;
  location?: { latitude: number; longitude: number; recorded_at?: string | null; updated_at?: string | null } | null;
};

type VexaMapProps = { drivers?: VexaMapDriver[]; height?: number | string };
const OBOLENSK_CENTER: [number, number] = [37.23, 54.98];

export default function VexaMap({ drivers = [], height = 430 }: VexaMapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const markersRef = useRef<Marker[]>([]);
  const [error, setError] = useState('');
  const [ready, setReady] = useState(false);
  const styleUrl = import.meta.env.VITE_VEXA_MAP_STYLE_URL?.trim() || '/maps/style.json';

  useEffect(() => {
    if (!styleUrl || !containerRef.current) return;
    let map: MapLibreMap;
    try {
      map = new maplibregl.Map({
        container: containerRef.current,
        style: styleUrl,
        center: OBOLENSK_CENTER,
        zoom: 13,
      });
      mapRef.current = map;
      map.addControl(new maplibregl.NavigationControl(), 'top-right');
      map.on('load', () => { setReady(true); setError(''); });
      map.on('error', () => setError('Не удалось загрузить данные VEXA MAP. Проверьте URL стиля и доступность тайлов.'));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Ошибка запуска VEXA MAP');
      return;
    }
    return () => {
      markersRef.current.forEach(marker => marker.remove());
      markersRef.current = [];
      mapRef.current = null;
      setReady(false);
      map.remove();
    };
  }, [styleUrl]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    markersRef.current.forEach(marker => marker.remove());
    markersRef.current = [];
    for (const driver of drivers) {
      const loc = driver.location;
      if (!driver.is_online || !loc || !Number.isFinite(loc.latitude) || !Number.isFinite(loc.longitude) ||
          Math.abs(loc.latitude) > 90 || Math.abs(loc.longitude) > 180) continue;
      const marker = new maplibregl.Marker({ color: '#54B6AA' })
        .setLngLat([loc.longitude, loc.latitude])
        .setPopup(new maplibregl.Popup().setText(driver.username || 'Водитель VEXA'))
        .addTo(map);
      markersRef.current.push(marker);
    }
    return () => { markersRef.current.forEach(marker => marker.remove()); markersRef.current = []; };
  }, [drivers, ready]);

  return <div style={{ position: 'relative', width: '100%', height, minHeight: 300, borderRadius: 12, overflow: 'hidden', background: 'var(--vexa-surface-2)' }}>
    <div ref={containerRef} style={{ width: '100%', height: '100%' }} />
    {!styleUrl && <div style={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center', padding: 24, textAlign: 'center' }}>
      VEXA MAP: задайте VITE_VEXA_MAP_STYLE_URL для подключения собственного сервера карт.
    </div>}
    {error && <div role="alert" style={{ position: 'absolute', bottom: 10, left: 10, right: 10, padding: 12, background: 'var(--vexa-surface)', color: 'var(--vexa-danger)' }}>{error}</div>}
  </div>;
}
