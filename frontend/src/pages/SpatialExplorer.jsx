import React, { useEffect, useMemo, useState } from 'react';
import {
  MapContainer, TileLayer, CircleMarker, Circle, Marker, Popup, GeoJSON, Polyline, Polygon,
  useMap, useMapEvents,
} from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { spatialService } from '../services/spatial';

delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
});

const MODES = [
  { id: 'nearby', label: 'Nearby places' },
  { id: 'adjacent', label: 'Adjacent roads' },
  { id: 'summary', label: 'Area summary' },
  { id: 'route', label: 'Along a route' },
  { id: 'area', label: 'Inside an area' },
  { id: 'compare', label: 'Compare areas' },
  { id: 'nearest', label: 'Nearest to each' },
  { id: 'distance', label: 'City distance' },
];

const CATEGORIES = [
  'hospital', 'clinic', 'pharmacy', 'school', 'college', 'university', 'fuel', 'police', 'fire_station',
];

const CATEGORY_COLORS = {
  hospital: '#ef4444', clinic: '#f97316', pharmacy: '#a855f7', school: '#3b82f6',
  college: '#6366f1', university: '#0ea5e9', fuel: '#eab308', police: '#1f2937', fire_station: '#dc2626',
};

const PRESETS = [
  { label: 'T Nagar, Chennai', lat: 13.0418, lon: 80.2341 },
  { label: 'PSG Tech, Coimbatore', lat: 11.0247, lon: 77.0028 },
  { label: 'Marina Beach, Chennai', lat: 13.0500, lon: 80.2824 },
];

const SINGLE_POINT_MODES = ['nearby', 'adjacent', 'summary'];
const MAX_NEAREST_POINTS = 10;
const MAX_POLYGON_POINTS = 50;

const fmtDistance = m => (m >= 1000 ? `${(m / 1000).toFixed(2)} km` : `${Math.round(m)} m`);
const toParam = pts => pts.map(p => `${p.lat},${p.lon}`).join(';');

function ClickToPick({ onPick }) {
  useMapEvents({ click: e => onPick({ lat: e.latlng.lat, lon: e.latlng.lng }) });
  return null;
}

function FitTo({ bounds }) {
  const map = useMap();
  useEffect(() => {
    if (bounds && bounds.isValid()) map.fitBounds(bounds, { padding: [40, 40], maxZoom: 16 });
  }, [bounds, map]);
  return null;
}

const Field = ({ label, children }) => (
  <label className="block text-xs text-gray-500 mb-3">
    <span className="block mb-1 font-medium text-gray-600">{label}</span>
    {children}
  </label>
);

const inputCls = 'w-full text-sm border border-gray-300 rounded-md px-2.5 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500';

const PlaceRow = ({ item, right, sub }) => (
  <li className="text-sm border-b border-gray-100 pb-1.5">
    <div className="flex justify-between gap-2">
      <span className="truncate">
        <span className="inline-block w-2 h-2 rounded-full mr-2" style={{ background: CATEGORY_COLORS[item.category] }} />
        {item.name || <em className="text-gray-400">unnamed {item.category}</em>}
      </span>
      <span className="text-gray-500 shrink-0">{right}</span>
    </div>
    {sub && <div className="text-[11px] text-gray-400 ml-4">{sub}</div>}
  </li>
);

const PlaceMarker = ({ item, children, radius = 8 }) => (
  <CircleMarker center={[item.lat, item.lon]} radius={radius}
    pathOptions={{ color: '#fff', weight: 2, fillColor: CATEGORY_COLORS[item.category] || '#555', fillOpacity: 0.95 }}>
    <Popup><strong>{item.name || `Unnamed ${item.category}`}</strong><br />{children}</Popup>
  </CircleMarker>
);

export const SpatialExplorer = () => {
  const [mode, setMode] = useState('nearby');
  const [point, setPoint] = useState(PRESETS[0]);
  const [place, setPlace] = useState('');
  const [category, setCategory] = useState('hospital');
  const [radius, setRadius] = useState(2000);
  const [routeFrom, setRouteFrom] = useState('T Nagar, Chennai');
  const [routeTo, setRouteTo] = useState('Marina Beach, Chennai');
  const [routeType, setRouteType] = useState('shortest');
  const [corridor, setCorridor] = useState(500);
  const [fromCity, setFromCity] = useState('Chennai');
  const [toCity, setToCity] = useState('Coimbatore');
  const [clicks, setClicks] = useState([]);                       // polygon vertices / nearest-each points
  const [circles, setCircles] = useState({ a: null, b: null });   // compare areas
  const [radiusA, setRadiusA] = useState(2000);
  const [radiusB, setRadiusB] = useState(2000);
  const [nextCircle, setNextCircle] = useState('a');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  const switchMode = id => {
    setMode(id); setResult(null); setError(null); setClicks([]);
    setCircles({ a: null, b: null }); setNextCircle('a');
  };

  const handleMapClick = p => {
    setResult(null);
    if (SINGLE_POINT_MODES.includes(mode)) {
      setPlace(''); setPoint(p);
    } else if (mode === 'area') {
      setClicks(c => (c.length < MAX_POLYGON_POINTS ? [...c, p] : c));
    } else if (mode === 'nearest') {
      setClicks(c => (c.length < MAX_NEAREST_POINTS ? [...c, p] : c));
    } else if (mode === 'compare') {
      setCircles(c => ({ ...c, [nextCircle]: p }));
      setNextCircle(n => (n === 'a' ? 'b' : 'a'));
    }
  };

  const canRun = (() => {
    if (mode === 'area') return clicks.length >= 3;
    if (mode === 'nearest') return clicks.length >= 1;
    if (mode === 'compare') return Boolean(circles.a && circles.b);
    return true;
  })();

  const run = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    const where = place.trim() ? { place: place.trim() } : { lat: point.lat, lon: point.lon };
    const cat = category || undefined;
    let res;
    if (mode === 'nearby') {
      res = await spatialService.nearby({ ...where, radius_m: radius, category: cat, limit: 50 });
    } else if (mode === 'adjacent') {
      res = await spatialService.adjacentRoads(where);
    } else if (mode === 'summary') {
      res = await spatialService.summary({ ...where, radius_m: radius });
    } else if (mode === 'route') {
      res = await spatialService.alongRoute({
        origin: routeFrom, destination: routeTo, category: cat,
        distance_m: corridor, route_type: routeType,
      });
    } else if (mode === 'area') {
      res = await spatialService.withinArea({ polygon: toParam(clicks), category: cat });
    } else if (mode === 'compare') {
      res = await spatialService.compareAreas({
        lat1: circles.a.lat, lon1: circles.a.lon, radius1_m: radiusA,
        lat2: circles.b.lat, lon2: circles.b.lon, radius2_m: radiusB,
      });
    } else if (mode === 'nearest') {
      res = await spatialService.nearestEach({ points: toParam(clicks), category: cat });
    } else {
      res = await spatialService.distance({ from: fromCity, to: toCity });
    }
    if (res?.success) {
      setResult(res);
      if (res.center) setPoint({ lat: res.center.lat, lon: res.center.lon });
    } else {
      setError(res?.error || 'Request failed');
    }
    setLoading(false);
  };

  const bounds = useMemo(() => {
    if (!result) return null;
    const b = L.latLngBounds([]);
    if (mode === 'nearby') {
      b.extend([result.center.lat, result.center.lon]);
      result.items.forEach(i => b.extend([i.lat, i.lon]));
    } else if (mode === 'adjacent') {
      [result.road, ...result.adjacent].forEach(r =>
        r.geometry.coordinates.forEach(([lon, lat]) => b.extend([lat, lon])));
    } else if (mode === 'summary') {
      result.buffer.coordinates[0].forEach(([lon, lat]) => b.extend([lat, lon]));
    } else if (mode === 'route') {
      result.route.path.forEach(([lat, lon]) => b.extend([lat, lon]));
    } else if (mode === 'area') {
      clicks.forEach(p => b.extend([p.lat, p.lon]));
    } else if (mode === 'compare') {
      result.union.coordinates.flat(2).forEach(c => {
        if (Array.isArray(c) && c.length === 2) b.extend([c[1], c[0]]);
      });
    } else if (mode === 'nearest') {
      result.items.forEach(i => { b.extend([i.lat, i.lon]); b.extend([i.from.lat, i.from.lon]); });
    } else {
      b.extend([result.from.lat, result.from.lon]);
      b.extend([result.to.lat, result.to.lon]);
    }
    return b;
  }, [result, mode, clicks]);

  const usesPoint = SINGLE_POINT_MODES.includes(mode);
  const usesRadius = mode === 'nearby' || mode === 'summary';
  const usesCategory = ['nearby', 'route', 'area', 'nearest'].includes(mode);
  const clicksReady = mode === 'area' || mode === 'nearest' || mode === 'compare';

  return (
    <div className="flex h-full">
      <aside className="w-96 shrink-0 border-r border-gray-200 overflow-y-auto p-4">
        <h2 className="text-lg font-semibold text-gray-900">Spatial Explorer</h2>
        <p className="text-xs text-gray-400 mb-3">PostGIS queries on the road network and places.</p>

        <div className="grid grid-cols-2 gap-1.5 mb-4">
          {MODES.map(m => (
            <button key={m.id} onClick={() => switchMode(m.id)}
              className={`text-xs px-2 py-1.5 rounded-md transition ${mode === m.id
                ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'}`}>
              {m.label}
            </button>
          ))}
        </div>

        {usesPoint && (
          <>
            <Field label="Place name (optional)">
              <input className={inputCls} value={place} placeholder="e.g. PSG College of Technology, Coimbatore"
                onChange={e => setPlace(e.target.value)} />
            </Field>
            <div className="text-xs text-gray-500 mb-1">
              {place.trim()
                ? 'Using the place name above.'
                : `Click the map to pick a point: ${point.lat.toFixed(4)}, ${point.lon.toFixed(4)}`}
            </div>
            <div className="flex flex-wrap gap-1.5 mb-3">
              {PRESETS.map(p => (
                <button key={p.label} onClick={() => { setPlace(''); setPoint(p); setResult(null); }}
                  className="text-[11px] px-2 py-1 rounded-full bg-gray-100 hover:bg-gray-200 text-gray-600">
                  {p.label}
                </button>
              ))}
            </div>
          </>
        )}

        {usesCategory && (
          <Field label="Category">
            <select className={inputCls} value={category} onChange={e => setCategory(e.target.value)}>
              <option value="">All</option>
              {CATEGORIES.map(c => <option key={c} value={c}>{c.replace('_', ' ')}</option>)}
            </select>
          </Field>
        )}

        {usesRadius && (
          <Field label={`Radius: ${fmtDistance(radius)}`}>
            <input type="range" min="250" max="5000" step="250" value={radius}
              onChange={e => setRadius(Number(e.target.value))} className="w-full" />
          </Field>
        )}

        {mode === 'route' && (
          <>
            <Field label="From"><input className={inputCls} value={routeFrom} onChange={e => setRouteFrom(e.target.value)} /></Field>
            <Field label="To"><input className={inputCls} value={routeTo} onChange={e => setRouteTo(e.target.value)} /></Field>
            <Field label="Route type">
              <select className={inputCls} value={routeType} onChange={e => setRouteType(e.target.value)}>
                <option value="shortest">Shortest</option>
                <option value="fuel">Fuel efficient</option>
                <option value="green">Green</option>
                <option value="avoid_main">Avoid main roads</option>
              </select>
            </Field>
            <Field label={`Within ${fmtDistance(corridor)} of the route`}>
              <input type="range" min="100" max="2000" step="100" value={corridor}
                onChange={e => setCorridor(Number(e.target.value))} className="w-full" />
            </Field>
          </>
        )}

        {mode === 'area' && (
          <div className="text-xs text-gray-500 mb-3">
            Click the map to draw a polygon ({clicks.length} point{clicks.length === 1 ? '' : 's'}; at least 3).
            <div className="flex gap-2 mt-2">
              <button onClick={() => { setClicks(c => c.slice(0, -1)); setResult(null); }} disabled={!clicks.length}
                className="px-2 py-1 rounded bg-gray-100 hover:bg-gray-200 disabled:opacity-40">Undo</button>
              <button onClick={() => { setClicks([]); setResult(null); }} disabled={!clicks.length}
                className="px-2 py-1 rounded bg-gray-100 hover:bg-gray-200 disabled:opacity-40">Clear</button>
            </div>
          </div>
        )}

        {mode === 'compare' && (
          <>
            <div className="text-xs text-gray-500 mb-3">
              Click the map to place circle <strong>{nextCircle.toUpperCase()}</strong>
              {' '}(A: {circles.a ? 'set' : 'not set'}, B: {circles.b ? 'set' : 'not set'}). Clicking again moves them in turn.
            </div>
            <Field label={`Radius A: ${fmtDistance(radiusA)}`}>
              <input type="range" min="250" max="8000" step="250" value={radiusA}
                onChange={e => { setRadiusA(Number(e.target.value)); setResult(null); }} className="w-full" />
            </Field>
            <Field label={`Radius B: ${fmtDistance(radiusB)}`}>
              <input type="range" min="250" max="8000" step="250" value={radiusB}
                onChange={e => { setRadiusB(Number(e.target.value)); setResult(null); }} className="w-full" />
            </Field>
          </>
        )}

        {mode === 'nearest' && (
          <div className="text-xs text-gray-500 mb-3">
            Click the map to add points ({clicks.length}/{MAX_NEAREST_POINTS}).
            <div className="flex gap-2 mt-2">
              <button onClick={() => { setClicks(c => c.slice(0, -1)); setResult(null); }} disabled={!clicks.length}
                className="px-2 py-1 rounded bg-gray-100 hover:bg-gray-200 disabled:opacity-40">Undo</button>
              <button onClick={() => { setClicks([]); setResult(null); }} disabled={!clicks.length}
                className="px-2 py-1 rounded bg-gray-100 hover:bg-gray-200 disabled:opacity-40">Clear</button>
            </div>
          </div>
        )}

        {mode === 'distance' && (
          <>
            <Field label="From city"><input className={inputCls} value={fromCity} onChange={e => setFromCity(e.target.value)} /></Field>
            <Field label="To city"><input className={inputCls} value={toCity} onChange={e => setToCity(e.target.value)} /></Field>
          </>
        )}

        <button onClick={run} disabled={loading || !canRun}
          className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-medium py-2 rounded-md transition">
          {loading ? 'Running…' : 'Run query'}
        </button>

        {error && <div className="mt-3 text-xs text-red-700 bg-red-50 border border-red-200 rounded-md p-2.5">{error}</div>}

        {result && mode === 'nearby' && (
          <div className="mt-4">
            <div className="text-xs font-medium text-gray-600 mb-2">
              {result.count} result{result.count === 1 ? '' : 's'} within {fmtDistance(result.radius_m)}
            </div>
            <ul className="space-y-1.5">
              {result.items.map(i => (
                <PlaceRow key={`${i.osm_type}-${i.osm_id}`} item={i} right={fmtDistance(i.distance_m)} />
              ))}
            </ul>
          </div>
        )}

        {result && mode === 'adjacent' && (
          <div className="mt-4 text-sm">
            <div className="text-xs font-medium text-gray-600 mb-1">Selected road</div>
            <div className="mb-3">{result.road.name || 'Unnamed road'} <span className="text-gray-400">· {result.road.highway} · {fmtDistance(result.road.length_m)}</span></div>
            <div className="text-xs font-medium text-gray-600 mb-1">{result.adjacent.length} adjacent segments</div>
            <ul className="space-y-1">
              {result.adjacent.map(a => (
                <li key={a.edge_id} className="text-gray-700">{a.name || 'Unnamed road'} <span className="text-gray-400">· {a.highway} · {fmtDistance(a.length_m)}</span></li>
              ))}
            </ul>
          </div>
        )}

        {result && mode === 'summary' && (
          <div className="mt-4 text-sm">
            <div className="text-xs font-medium text-gray-600 mb-1">Places within {fmtDistance(result.radius_m)}</div>
            {Object.keys(result.pois).length === 0
              ? <div className="text-gray-400 mb-3">No places loaded for this area.</div>
              : <ul className="mb-3">{Object.entries(result.pois).map(([k, v]) => (
                  <li key={k} className="flex justify-between"><span>{k.replace('_', ' ')}</span><span className="text-gray-500">{v}</span></li>))}
                </ul>}
            <div className="text-xs font-medium text-gray-600 mb-1">Roads by type</div>
            <ul>{result.roads.map(r => (
              <li key={r.highway} className="flex justify-between"><span>{r.highway}</span>
                <span className="text-gray-500">{r.segments} segments · {(r.length_m / 1000).toFixed(1)} km</span></li>))}
            </ul>
          </div>
        )}

        {result && mode === 'route' && (
          <div className="mt-4">
            <div className="text-sm text-gray-900 font-medium">
              {(result.route.distance_m / 1000).toFixed(1)} km · {Math.round(result.route.estimated_time_min)} min
            </div>
            <div className="text-xs text-gray-500 mb-2">
              {result.count} place{result.count === 1 ? '' : 's'} within {fmtDistance(result.distance_m)} of the route, in travel order
            </div>
            <ul className="space-y-1.5">
              {result.items.map(i => (
                <PlaceRow key={`${i.osm_type}-${i.osm_id}`} item={i}
                  right={`${(i.along_m / 1000).toFixed(1)} km`}
                  sub={`${Math.round(i.distance_from_route_m)} m off the route`} />
              ))}
            </ul>
          </div>
        )}

        {result && mode === 'area' && (
          <div className="mt-4 text-sm">
            <div className="text-gray-900 font-medium">{result.area_km2} km² · {result.count} place{result.count === 1 ? '' : 's'} inside</div>
            <ul className="my-2 text-xs text-gray-600">
              {Object.entries(result.counts).map(([k, v]) => (
                <li key={k} className="flex justify-between"><span>{k.replace('_', ' ')}</span><span>{v}</span></li>))}
            </ul>
            {result.most_central && (
              <div className="text-xs bg-amber-50 border border-amber-200 rounded-md p-2 mb-3">
                Most central: <strong>{result.most_central.name || `unnamed ${result.most_central.category}`}</strong>
                {' '}({Math.round(result.most_central.distance_to_centroid_m)} m from the centre)
              </div>
            )}
            <ul className="space-y-1.5">
              {result.items.slice(0, 50).map(i => (
                <PlaceRow key={`${i.osm_type}-${i.osm_id}`} item={i}
                  right={`${Math.round(i.distance_to_centroid_m)} m from centre`} />
              ))}
            </ul>
          </div>
        )}

        {result && mode === 'compare' && (
          <div className="mt-4 text-sm">
            <ul className="space-y-1">
              {[['Area A', result.area_km2.a], ['Area B', result.area_km2.b],
                ['Union', result.area_km2.union], ['Overlap (intersection)', result.area_km2.intersection],
                ['Symmetric difference', result.area_km2.symmetric_difference]].map(([k, v]) => (
                <li key={k} className="flex justify-between"><span>{k}</span><span className="text-gray-600">{v} km²</span></li>))}
            </ul>
            <div className="text-xs text-gray-500 mt-2">Overlap is {result.overlap_pct_of_smaller}% of the smaller area.</div>
          </div>
        )}

        {result && mode === 'nearest' && (
          <ul className="mt-4 space-y-1.5">
            {result.items.map(i => (
              <PlaceRow key={i.index} item={i} right={fmtDistance(i.distance_m)}
                sub={`from point ${i.index + 1} (${i.from.lat.toFixed(4)}, ${i.from.lon.toFixed(4)})`} />
            ))}
          </ul>
        )}

        {result && mode === 'distance' && (
          <div className="mt-4 text-sm">
            <div className="text-2xl font-semibold text-gray-900">{result.distance_km} km</div>
            <div className="text-gray-500">straight-line between {result.from.name} and {result.to.name}</div>
          </div>
        )}
      </aside>

      <div className="flex-1">
        <MapContainer center={[point.lat, point.lon]} zoom={13} style={{ height: '100%', width: '100%' }}>
          <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" attribution="&copy; OpenStreetMap contributors" />
          {(usesPoint || clicksReady) && <ClickToPick onPick={handleMapClick} />}
          <FitTo bounds={bounds} />
          {usesPoint && <Marker position={[point.lat, point.lon]} />}

          {result && mode === 'nearby' && result.items.map(i => (
            <PlaceMarker key={`${i.osm_type}-${i.osm_id}`} item={i}>{i.category} · {fmtDistance(i.distance_m)}</PlaceMarker>
          ))}

          {result && mode === 'adjacent' && (
            <>
              {result.adjacent.map(a => (
                <GeoJSON key={`a-${a.edge_id}`} data={a.geometry} style={{ color: '#f97316', weight: 5 }} />
              ))}
              <GeoJSON key={`r-${result.road.edge_id}`} data={result.road.geometry} style={{ color: '#2563eb', weight: 7 }} />
            </>
          )}

          {result && mode === 'summary' && (
            <GeoJSON key={`b-${result.radius_m}-${result.center.lat}`} data={result.buffer}
              style={{ color: '#2563eb', weight: 2, fillColor: '#3b82f6', fillOpacity: 0.12 }} />
          )}

          {result && mode === 'route' && (
            <>
              <Polyline positions={result.route.path} pathOptions={{ color: '#2563eb', weight: 5, opacity: 0.8 }} />
              <Marker position={[result.origin.lat, result.origin.lon]}><Popup>Start: {result.origin.name}</Popup></Marker>
              <Marker position={[result.destination.lat, result.destination.lon]}><Popup>End: {result.destination.name}</Popup></Marker>
              {result.items.map(i => (
                <PlaceMarker key={`${i.osm_type}-${i.osm_id}`} item={i} radius={7}>
                  {(i.along_m / 1000).toFixed(1)} km along · {Math.round(i.distance_from_route_m)} m off the route
                </PlaceMarker>
              ))}
            </>
          )}

          {mode === 'area' && clicks.length > 0 && (
            <>
              {clicks.length >= 3
                ? <Polygon positions={clicks.map(p => [p.lat, p.lon])}
                    pathOptions={{ color: '#2563eb', weight: 2, fillColor: '#3b82f6', fillOpacity: 0.12 }} />
                : <Polyline positions={clicks.map(p => [p.lat, p.lon])} pathOptions={{ color: '#2563eb', weight: 2 }} />}
              {clicks.map((p, idx) => (
                <CircleMarker key={idx} center={[p.lat, p.lon]} radius={4}
                  pathOptions={{ color: '#2563eb', fillColor: '#fff', fillOpacity: 1 }} />
              ))}
            </>
          )}
          {result && mode === 'area' && (
            <>
              {result.items.map(i => (
                <PlaceMarker key={`${i.osm_type}-${i.osm_id}`} item={i} radius={6}>
                  {i.category} · {Math.round(i.distance_to_centroid_m)} m from the centre
                </PlaceMarker>
              ))}
              <CircleMarker center={[result.centroid.lat, result.centroid.lon]} radius={5}
                pathOptions={{ color: '#111827', fillColor: '#111827', fillOpacity: 1 }}>
                <Popup>Centre of the area</Popup>
              </CircleMarker>
              {result.most_central && (
                <CircleMarker center={[result.most_central.lat, result.most_central.lon]} radius={13}
                  pathOptions={{ color: '#f59e0b', weight: 3, fillOpacity: 0 }}>
                  <Popup>Most central: {result.most_central.name || result.most_central.category}</Popup>
                </CircleMarker>
              )}
            </>
          )}

          {mode === 'compare' && (
            <>
              {circles.a && <Circle center={[circles.a.lat, circles.a.lon]} radius={radiusA}
                pathOptions={{ color: '#2563eb', weight: 2, fillColor: '#3b82f6', fillOpacity: 0.12 }} />}
              {circles.b && <Circle center={[circles.b.lat, circles.b.lon]} radius={radiusB}
                pathOptions={{ color: '#9333ea', weight: 2, fillColor: '#a855f7', fillOpacity: 0.12 }} />}
              {circles.a && <Marker position={[circles.a.lat, circles.a.lon]}><Popup>Area A</Popup></Marker>}
              {circles.b && <Marker position={[circles.b.lat, circles.b.lon]}><Popup>Area B</Popup></Marker>}
            </>
          )}
          {result && mode === 'compare' && result.area_km2.intersection > 0 && (
            <GeoJSON key={`i-${result.area_km2.intersection}`} data={result.intersection}
              style={{ color: '#ea580c', weight: 2, fillColor: '#f97316', fillOpacity: 0.45 }} />
          )}

          {mode === 'nearest' && clicks.map((p, idx) => (
            <Marker key={idx} position={[p.lat, p.lon]}><Popup>Point {idx + 1}</Popup></Marker>
          ))}
          {result && mode === 'nearest' && result.items.map(i => (
            <React.Fragment key={i.index}>
              <Polyline positions={[[i.from.lat, i.from.lon], [i.lat, i.lon]]}
                pathOptions={{ color: '#6b7280', weight: 2, dashArray: '4 6' }} />
              <PlaceMarker item={i}>nearest to point {i.index + 1} · {fmtDistance(i.distance_m)}</PlaceMarker>
            </React.Fragment>
          ))}

          {result && mode === 'distance' && (
            <>
              <Marker position={[result.from.lat, result.from.lon]}><Popup>{result.from.name}</Popup></Marker>
              <Marker position={[result.to.lat, result.to.lon]}><Popup>{result.to.name}</Popup></Marker>
              <Polyline positions={result.line.coordinates.map(([lon, lat]) => [lat, lon])}
                pathOptions={{ color: '#2563eb', weight: 3, dashArray: '8 8' }} />
            </>
          )}
        </MapContainer>
      </div>
    </div>
  );
};
