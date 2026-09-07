import React, { useState, useEffect } from 'react';
import { SearchBar }    from '../components/SearchBar';
import { RouteMap }     from '../components/RouteMap';
import { RouteDetails } from '../components/RouteDetails';
import { ErrorAlert }   from '../components/ErrorAlert';
import { routeService } from '../services/api';
import { Navigation2 }  from 'lucide-react';

export const HomePage = () => {
  const [origin, setOrigin]           = useState('');
  const [destination, setDestination] = useState('');
  const [routeType, setRouteType]     = useState('shortest');
  const [vehicleType, setVehicleType] = useState('car');
  const [nlQuery, setNlQuery]         = useState('');
  const [route, setRoute]             = useState(null);
  const [isLoading, setIsLoading]     = useState(false);
  const [error, setError]             = useState(null);
  const [smartResult, setSmartResult] = useState(null);   // full /route/smart response (all candidates)
  const [activeIdx, setActiveIdx]     = useState(0);

  useEffect(() => {
    try {
      const stored = localStorage.getItem('selectedRoute');
      if (stored) {
        const p = JSON.parse(stored);
        if (p?.success) setRoute(p);
        localStorage.removeItem('selectedRoute');
      }
    } catch {}
  }, []);

  // Builds the RouteDetails-shaped object for one candidate from a /route/smart response
  const buildSmartRoute = (res, candidate) => ({
    success: true,
    cache_hit: false,
    distance_km: parseFloat((candidate.distance_m / 1000).toFixed(2)),
    distance_m: candidate.distance_m,
    estimated_time_min: candidate.eta_min,
    algorithm_time_ms: null,
    nodes_explored: null,
    path_nodes: candidate.path_coordinates?.length,
    origin: res.origin,
    destination: res.destination,
    path_coordinates: candidate.path_coordinates,
    route_type: 'smart',
    vehicle_type: vehicleType,
    // smart-specific fields
    label: candidate.label,
    explanation: candidate.explanation,
    scores: candidate.score,
    constraints: res.constraints,
    cost_formula: res.cost_formula,
    calculation_time_s: res.calculation_time_s,
  });

  const selectRoute = (idx) => {
    if (!smartResult?.routes?.[idx]) return;
    setActiveIdx(idx);
    setRoute(buildSmartRoute(smartResult, smartResult.routes[idx]));
  };

  const handleSearch = async () => {
    if (!origin.trim() || !destination.trim()) {
      setError('Please enter both origin and destination');
      return;
    }
    setIsLoading(true);
    setError(null);
    setRoute(null);
    setSmartResult(null);
    setActiveIdx(0);

    try {
      if (nlQuery.trim()) {
        // NL pipeline — LLM extracts constraints, Yen's K-Shortest + A* run with the dynamic cost fn
        const res = await routeService.smartRoute({
          query: nlQuery,
          origin,
          destination,
          vehicle_type: vehicleType,
          time_of_day: new Date().getHours(),
        });

        if (!res.success || !res.routes?.length) {
          setError(res.error || 'No routes found');
          return;
        }

        setSmartResult(res);
        setRoute(buildSmartRoute(res, res.routes[0]));
      } else {
        const res = await routeService.calculateRoute(
          origin, destination, null, null, routeType, undefined, vehicleType
        );
        if (res.success) setRoute(res);
        else setError(res.error || 'Failed to calculate route');
      }
    } catch (err) {
      setError(err?.error || err?.message || 'An error occurred');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex h-full">

      {/* Sidebar */}
      <div className="w-80 flex-shrink-0 bg-white border-r border-gray-100 flex flex-col overflow-hidden shadow-sm z-10">

        <div className="p-4 border-b border-gray-100">
          <SearchBar
            origin={origin} destination={destination}
            routeType={routeType} vehicleType={vehicleType}
            nlQuery={nlQuery}
            onOriginChange={setOrigin} onDestinationChange={setDestination}
            onRouteTypeChange={setRouteType} onVehicleTypeChange={setVehicleType}
            onNlQueryChange={setNlQuery}
            onSearch={handleSearch} isLoading={isLoading}
          />
          {error && (
            <div className="mt-3">
              <ErrorAlert error={error} onClose={() => setError(null)} />
            </div>
          )}
        </div>

        <div className="flex-1 overflow-y-auto">
          {route ? (
            <div className="p-4 space-y-3">
              {smartResult?.routes?.length > 1 && (
                <div className="flex flex-col gap-1.5">
                  <p className="text-xs font-medium text-gray-400">
                    {smartResult.routes.length} route options
                  </p>
                  {smartResult.routes.map((r, idx) => (
                    <button
                      key={r.route_id || idx}
                      onClick={() => selectRoute(idx)}
                      className={`text-left text-xs rounded-lg px-3 py-2 border transition-colors ${
                        idx === activeIdx
                          ? 'bg-blue-50 border-blue-200 text-blue-700'
                          : 'bg-white border-gray-100 text-gray-500 hover:border-gray-200'
                      }`}
                    >
                      <span className="font-semibold">#{r.rank} {r.label}</span>
                      {' — '}{r.eta_min} min · {(r.distance_m / 1000).toFixed(1)} km · {r.semantic_class}
                    </button>
                  ))}
                </div>
              )}
              <RouteDetails route={route} />
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-48 text-center px-6">
              <div className="w-12 h-12 rounded-full bg-gray-50 flex items-center justify-center mb-3">
                <Navigation2 className="w-5 h-5 text-gray-300" />
              </div>
              <p className="text-sm text-gray-400">Enter a route to get started</p>
            </div>
          )}
        </div>
      </div>

      {/* Map */}
      <div className="flex-1 relative">
        <RouteMap
          origin={route?.origin}
          destination={route?.destination}
          pathCoordinates={route?.path_coordinates}
          routes={smartResult?.routes?.length > 1 ? smartResult.routes : null}
          activeRouteIndex={activeIdx}
        />
      </div>

    </div>
  );
};
