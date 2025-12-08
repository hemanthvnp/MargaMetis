import React, { useState, useEffect } from 'react';
import { SearchBar } from '../components/SearchBar';
import { RouteMap } from '../components/RouteMap';
import { RouteDetails } from '../components/RouteDetails';
import { ErrorAlert } from '../components/ErrorAlert';
import { routeService } from '../services/api';

export const HomePage = () => {
  const [origin, setOrigin] = useState('');
  const [destination, setDestination] = useState('');
  const [routeType, setRouteType] = useState('shortest');
  const [vehicleType, setVehicleType] = useState('car');
  const [route, setRoute] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    // Load selected route from localStorage if present
    try {
      const stored = localStorage.getItem('selectedRoute');
      if (stored) {
        const parsed = JSON.parse(stored);
        if (parsed && parsed.success) {
          setRoute(parsed);
        }
        localStorage.removeItem('selectedRoute');
      }
    } catch (e) {
      // ignore
    }
  }, []);

  const handleSearch = async () => {
    if (!origin.trim() || !destination.trim()) {
      setError('Please enter both origin and destination');
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const result = await routeService.calculateRoute(origin, destination, null, null, routeType, undefined, vehicleType);
      if (result.success) {
        setRoute(result);
      } else {
        setError(result.error || 'Failed to calculate route');
      }
    } catch (err) {
      setError(err.error || 'An error occurred while calculating the route');
      console.error('Route calculation error:', err);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 py-8 sm:px-6 lg:px-8">
        {/* Search Section */}
        <div className="mb-8">
          <SearchBar
            origin={origin}
            destination={destination}
            routeType={routeType}
            vehicleType={vehicleType}
            onOriginChange={setOrigin}
            onDestinationChange={setDestination}
            onRouteTypeChange={setRouteType}
            onVehicleTypeChange={setVehicleType}
            onSearch={handleSearch}
            isLoading={isLoading}
          />
        </div>

        {/* Error Alert */}
        {error && (
          <ErrorAlert error={error} onClose={() => setError(null)} />
        )}

        {/* Main Content */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Map */}
          <div className="lg:col-span-2">
            <div className="bg-white rounded-lg shadow-lg overflow-hidden" style={{ height: '500px' }}>
              <RouteMap
                origin={route?.origin}
                destination={route?.destination}
                pathCoordinates={route?.path_coordinates}
              />
            </div>
          </div>

          {/* Route Details */}
          <div className="lg:col-span-1">
            {route ? (
              <RouteDetails route={route} />
            ) : (
              <div className="bg-white rounded-lg shadow-lg p-6 text-center text-gray-500">
                <p>Search for a route to see details here</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
