
import React, { useEffect, useRef, useState } from 'react';

declare global {
  interface Window {
    mapgl?: MapGLNamespace;
  }

  interface ImportMetaEnv {
    readonly VITE_2GIS_MAPGL_KEY?: string;
  }

  interface ImportMeta {
    readonly env: ImportMetaEnv;
  }
}

type MapGLMarker = {
  destroy: () => void;
};

type MapGLMap = {
  destroy: () => void;
};

type MapGLNamespace = {
  Map: new (
    container: HTMLElement,
    options: {
      center: [number, number];
      zoom: number;
      key: string;
      enableTrackResize?: boolean;
      zoomControl?: string;
    },
  ) => MapGLMap;

  Marker: new (
    map: MapGLMap,
    options: {
      coordinates: [number, number];
      label?: {
        text: string;
      };
    },
  ) => MapGLMarker;
};

export type VexaMapDriver = {
  user_id: string;
  username: string;
  phone?: string | null;
  is_online: boolean;
  location?: {
    latitude: number;
    longitude: number;
    recorded_at?: string | null;
    updated_at?: string | null;
  } | null;
};

type VexaMapProps = {
  drivers?: VexaMapDriver[];
  apiKey?: string;
  height?: number | string;
};

const MAP_SCRIPT_URL = 'https://mapgl.2gis.com/api/js/v1';
const MAP_SCRIPT_ID = 'vexa-2gis-mapgl-script';

// Приблизительный центр пилотной зоны Оболенска.
const OBOLENSK_CENTER: [number, number] = [37.23, 54.98];

let mapglLoadPromise: Promise<MapGLNamespace> | null = null;

function loadMapGL(): Promise<MapGLNamespace> {
  if (window.mapgl) {
    return Promise.resolve(window.mapgl);
  }

  if (mapglLoadPromise) {
    return mapglLoadPromise;
  }

  mapglLoadPromise = new Promise((resolve, reject) => {
    let script = document.getElementById(
      MAP_SCRIPT_ID,
    ) as HTMLScriptElement | null;

    const handleLoad = () => {
      if (window.mapgl) {
        resolve(window.mapgl);
      } else {
        mapglLoadPromise = null;
        reject(new Error('Библиотека 2ГИС загрузилась некорректно'));
      }
    };

    const handleError = () => {
      mapglLoadPromise = null;
      reject(new Error('Не удалось загрузить библиотеку 2ГИС'));
    };

    if (!script) {
      script = document.createElement('script');
      script.id = MAP_SCRIPT_ID;
      script.src = MAP_SCRIPT_URL;
      script.async = true;
      script.defer = true;
      document.head.appendChild(script);
    }

    script.addEventListener('load', handleLoad, { once: true });
    script.addEventListener('error', handleError, { once: true });
  });

  return mapglLoadPromise;
}

export default function VexaMap({
  drivers = [],
  apiKey,
  height = 430,
}: VexaMapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapGLMap | null>(null);
  const markersRef = useRef<MapGLMarker[]>([]);

  const [mapReady, setMapReady] = useState(false);
  const [loading, setLoading] = useState(false);
  const [mapError, setMapError] = useState('');

  const resolvedApiKey =
    apiKey?.trim() ||
    import.meta.env.VITE_2GIS_MAPGL_KEY?.trim() ||
    '';

  useEffect(() => {
    let cancelled = false;

    async function initializeMap() {
      if (!resolvedApiKey) {
        setMapReady(false);
        setLoading(false);
        setMapError('');
        return;
      }

      if (!containerRef.current) return;

      setLoading(true);
      setMapError('');

      try {
        const mapgl = await loadMapGL();

        if (cancelled || !containerRef.current) return;

        const map = new mapgl.Map(containerRef.current, {
          center: OBOLENSK_CENTER,
          zoom: 13,
          key: resolvedApiKey,
          enableTrackResize: true,
          zoomControl: 'topRight',
        });

        if (cancelled) {
          map.destroy();
          return;
        }

        mapRef.current = map;
        setMapReady(true);
      } catch (error) {
        if (!cancelled) {
          setMapError(
            error instanceof Error
              ? error.message
              : 'Не удалось инициализировать карту',
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    initializeMap();

    return () => {
      cancelled = true;

      markersRef.current.forEach(marker => marker.destroy());
      markersRef.current = [];

      mapRef.current?.destroy();
      mapRef.current = null;

      setMapReady(false);
    };
  }, [resolvedApiKey]);

  useEffect(() => {
    if (!mapReady || !mapRef.current || !window.mapgl) return;

    markersRef.current.forEach(marker => marker.destroy());
    markersRef.current = [];

    const activeDrivers = drivers.filter(driver => {
      const location = driver.location;

      return (
        driver.is_online &&
        location &&
        Number.isFinite(location.latitude) &&
        Number.isFinite(location.longitude) &&
        Math.abs(location.latitude) <= 90 &&
        Math.abs(location.longitude) <= 180
      );
    });

    activeDrivers.forEach(driver => {
      if (!driver.location || !window.mapgl || !mapRef.current) return;

      const marker = new window.mapgl.Marker(mapRef.current, {
        coordinates: [
          driver.location.longitude,
          driver.location.latitude,
        ],
        label: {
          text: driver.username || 'Водитель VEXA',
        },
      });

      markersRef.current.push(marker);
    });

    return () => {
      markersRef.current.forEach(marker => marker.destroy());
      markersRef.current = [];
    };
  }, [drivers, mapReady]);

  const wrapperStyle: React.CSSProperties = {
    position: 'relative',
    width: '100%',
    height,
    minHeight: 300,
    overflow: 'hidden',
    borderRadius: 12,
    border: '1px solid #e4eaf0',
    background: '#f3f6f8',
  };

  if (!resolvedApiKey) {
    return (
      <div style={{
        ...wrapperStyle,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 24,
        boxSizing: 'border-box',
      }}>
        <div style={{ textAlign: 'center', maxWidth: 380 }}>
          <div style={{
            width: 54,
            height: 54,
            margin: '0 auto 15px',
            borderRadius: 16,
            background: '#e5f4f2',
            color: '#159c8c',
            display: 'grid',
            placeItems: 'center',
            fontSize: 25,
            fontWeight: 800,
          }}>
            V
          </div>

          <h3 style={{
            margin: '0 0 8px',
            color: '#243447',
            fontSize: 17,
          }}>
            Карта VEXA · Оболенск
          </h3>

          <p style={{
            margin: 0,
            color: '#778596',
            fontSize: 13,
            lineHeight: 1.6,
          }}>
            Карта 2ГИС подготовлена к подключению.
            После настройки действующего API-ключа
            здесь появятся карта города и отметки водителей.
          </p>

          <div style={{
            display: 'inline-block',
            marginTop: 15,
            padding: '7px 12px',
            borderRadius: 20,
            background: '#fff3df',
            color: '#98651b',
            fontSize: 11,
            fontWeight: 700,
          }}>
            Ожидается подключение 2ГИС
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={wrapperStyle}>
      <div
        ref={containerRef}
        style={{
          width: '100%',
          height: '100%',
          minHeight: 300,
        }}
      />

      {loading && (
        <div style={{
          position: 'absolute',
          inset: 0,
          display: 'grid',
          placeItems: 'center',
          background: '#f3f6f8',
          color: '#526174',
          fontSize: 13,
        }}>
          Загрузка карты 2ГИС...
        </div>
      )}

      {mapError && (
        <div style={{
          position: 'absolute',
          inset: 0,
          display: 'grid',
          placeItems: 'center',
          padding: 24,
          boxSizing: 'border-box',
          background: '#f3f6f8',
        }}>
          <div style={{ textAlign: 'center', maxWidth: 360 }}>
            <strong style={{
              display: 'block',
              color: '#b42318',
              marginBottom: 8,
            }}>
              Карта 2ГИС временно недоступна
            </strong>
            <span style={{
              color: '#778596',
              fontSize: 12,
              lineHeight: 1.5,
            }}>
              {mapError}
            </span>
          </div>
        </div>
      )}

      {mapReady && (
        <div style={{
          position: 'absolute',
          left: 12,
          bottom: 12,
          padding: '7px 10px',
          borderRadius: 8,
          background: '#ffffffed',
          color: '#526174',
          fontSize: 11,
          boxShadow: '0 2px 8px #00000012',
          pointerEvents: 'none',
        }}>
          Водителей на карте: {drivers.filter(
            driver =>
              driver.is_online &&
              driver.location &&
              Number.isFinite(driver.location.latitude) &&
              Number.isFinite(driver.location.longitude),
          ).length}
        </div>
      )}
    </div>
  );
}
