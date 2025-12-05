import React from 'react';
import { Clock, Navigation, MapPin } from 'lucide-react';

export const RouteDetails = ({ route }) => {
    const vehicleTypeLabel = route.vehicle_type ? route.vehicle_type.charAt(0).toUpperCase() + route.vehicle_type.slice(1) : 'Car';
  if (!route) return null;

  return (
    <div className="w-full bg-white rounded-lg shadow-lg p-6">
      <h2 className="text-2xl font-bold mb-4 text-gray-800">Route Details</h2>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Distance */}
        <div className="bg-gradient-to-br from-blue-50 to-blue-100 rounded-lg p-4">
          <div className="flex items-center mb-2">
            <Navigation className="w-5 h-5 text-blue-600 mr-2" />
            <span className="text-gray-600 font-medium">Distance</span>
          </div>
          <p className="text-3xl font-bold text-blue-600">
            {route.distance_km} <span className="text-lg">km</span>
          </p>
          <p className="text-sm text-gray-600 mt-1">
            {route.distance_m.toLocaleString()} meters
          </p>
        </div>

        {/* Calculation Time */}
        <div className="bg-gradient-to-br from-green-50 to-green-100 rounded-lg p-4">
          <div className="flex items-center mb-2">
            <Clock className="w-5 h-5 text-green-600 mr-2" />
            <span className="text-gray-600 font-medium">Calculation Time</span>
          </div>
          <p className="text-3xl font-bold text-green-600">
            {route.calculation_time_s} <span className="text-lg">s</span>
          </p>
          <p className="text-sm text-gray-600 mt-1">seconds</p>
        </div>

        {/* Path Nodes */}
        <div className="bg-gradient-to-br from-purple-50 to-purple-100 rounded-lg p-4">
          <div className="flex items-center mb-2">
            <MapPin className="w-5 h-5 text-purple-600 mr-2" />
            <span className="text-gray-600 font-medium">Path Nodes</span>
          </div>
          <p className="text-3xl font-bold text-purple-600">{route.path_nodes}</p>
          <p className="text-sm text-gray-600 mt-1">intersection points</p>
        </div>
      </div>

      {/* Advanced Route Info */}
      <div className="mt-6 border-t pt-6">
        <h3 className="font-semibold text-gray-800 mb-3">Route Summary</h3>
        <div className="space-y-2">
          <div className="flex justify-between items-center">
            <span className="text-gray-600">From:</span>
            <span className="font-medium text-gray-800">{route.origin.name}</span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-gray-600">To:</span>
            <span className="font-medium text-gray-800">{route.destination.name}</span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-gray-600">Coordinates:</span>
            <span className="text-sm text-gray-600">
              ({route.origin.lat.toFixed(4)}, {route.origin.lon.toFixed(4)}) →
              ({route.destination.lat.toFixed(4)}, {route.destination.lon.toFixed(4)})
            </span>
          </div>
        </div>

        {/* Advanced Features */}
        <div className="mt-6">
          <h4 className="font-semibold text-gray-800 mb-2">Advanced Route Features</h4>
          <div className="space-y-2">
            <div className="flex justify-between items-center">
              <span className="text-gray-600">Route Type:</span>
              <span className="font-medium text-gray-800">{route.route_type?.replace('_', ' ') || 'Shortest'}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-600">Vehicle Type:</span>
              <span className="font-medium text-gray-800">{vehicleTypeLabel}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-600">Estimated Travel Time:</span>
              <span className="font-medium text-gray-800">{route.estimated_time_min} min</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-600">Best Hour (Least Traffic):</span>
              <span className="font-medium text-gray-800">{route.best_hour}:00</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-600">Best Time (min):</span>
              <span className="font-medium text-gray-800">{route.best_time_min} min</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-600">Traffic Prediction:</span>
              <span className="text-sm text-gray-600">{route.traffic_prediction ? route.traffic_prediction.map((v, i) => `${v.toFixed(2)}` ).join(', ') : 'N/A'}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
