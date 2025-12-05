import React, { useEffect, useState } from 'react';
import { userService } from '../services/user';

export const UserDashboard = () => {
  const [tab, setTab] = useState('history');
  const [items, setItems] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (tab === 'history') {
      loadHistory();
    }
  }, [tab]);

  const loadHistory = async () => {
    setLoading(true);
    const res = await userService.history(1, 50);
    if (res && res.success) {
      setItems(res.items || []);
      setError(null);
    } else {
      setError(res?.error || 'Failed to load history');
    }
    setLoading(false);
  };

  const viewOnMap = async (id) => {
    const res = await userService.historyItem(id);
    if (res && res.success) {
      try {
        localStorage.setItem('selectedRoute', JSON.stringify(res.result));
        window.location.href = '/';
      } catch (e) {
        setError('Could not open route on map');
      }
    } else {
      setError(res?.error || 'Failed to open history item');
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <h2 className="text-2xl font-bold mb-4">User Dashboard</h2>

      <div className="flex gap-2 mb-6">
        <button
          className={`px-3 py-1 rounded-md text-sm ${tab === 'history' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-700'}`}
          onClick={() => setTab('history')}
        >
          Search History
        </button>
        <button
          className={`px-3 py-1 rounded-md text-sm ${tab === 'features' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-700'}`}
          onClick={() => setTab('features')}
        >
          Advanced Features
        </button>
        <button
          className={`px-3 py-1 rounded-md text-sm ${tab === 'settings' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-700'}`}
          onClick={() => setTab('settings')}
        >
          Settings
        </button>
      </div>

      {error && <div className="text-red-600 mb-3">{error}</div>}

      {tab === 'history' && (
        <div className="bg-white rounded-lg shadow p-4">
          {loading ? (
            <div>Loading...</div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-gray-600">
                  <th className="py-2">Origin</th>
                  <th className="py-2">Destination</th>
                  <th className="py-2">Route Type</th>
                  <th className="py-2">Vehicle</th>
                  <th className="py-2">Distance (km)</th>
                  <th className="py-2">Time (min)</th>
                  <th className="py-2">Action</th>
                </tr>
              </thead>
              <tbody>
                {items.map((it) => (
                  <tr key={it.id} className="border-t">
                    <td className="py-2">{it.origin}</td>
                    <td className="py-2">{it.destination}</td>
                    <td className="py-2">{it.route_type}</td>
                    <td className="py-2">{it.vehicle_type}</td>
                    <td className="py-2">{(it.distance_m / 1000).toFixed(2)}</td>
                    <td className="py-2">{Math.round(it.estimated_time_min || 0)}</td>
                    <td className="py-2">
                      <button
                        onClick={() => viewOnMap(it.id)}
                        className="text-sm bg-blue-600 hover:bg-blue-700 text-white px-3 py-1 rounded-md"
                      >
                        View on Map
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {tab === 'features' && (
        <div className="bg-white rounded-lg shadow p-4 space-y-3">
          <h3 className="font-semibold">Available Features</h3>
          <ul className="list-disc pl-5 text-sm">
            <li>Cost-efficient, fuel-efficient, green, traffic-free routing</li>
            <li>Vehicle-specific travel times (car, bike, truck)</li>
            <li>Traffic prediction and best hour recommendation</li>
            <li>Map auto-fit to route bounds and India default</li>
            <li>Search history caching with instant reuse</li>
          </ul>
        </div>
      )}

      {tab === 'settings' && (
        <div className="bg-white rounded-lg shadow p-4 space-y-3">
          <h3 className="font-semibold">Account Settings</h3>
          <p className="text-sm text-gray-600">Manage your profile. (More controls can be added: change password, update details.)</p>
        </div>
      )}
    </div>
  );
};
