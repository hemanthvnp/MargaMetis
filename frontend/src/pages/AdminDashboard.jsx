import React, { useEffect, useState } from 'react';
import { adminService } from '../services/admin';

export const AdminDashboard = () => {
  const [stats, setStats] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      setLoading(true);
      const res = await adminService.stats();
      if (res && res.success) {
        setStats(res);
        setError(null);
      } else {
        setError(res?.error || 'Failed to load stats');
      }
      setLoading(false);
    })();
  }, []);

  if (loading) {
    return <div className="max-w-7xl mx-auto px-4 py-8">Loading stats...</div>;
  }

  if (error) {
    return <div className="max-w-7xl mx-auto px-4 py-8 text-red-600">{error}</div>;
  }

  const { totals, top_origins, top_destinations, top_route_types, top_pairs, hourly_distribution } = stats || {};

  return (
    <div className="max-w-7xl mx-auto px-4 py-8 space-y-8">
      <h2 className="text-2xl font-bold">Admin Dashboard</h2>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-gray-500 text-sm">Total Searches</div>
          <div className="text-3xl font-semibold">{totals?.searches ?? 0}</div>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-gray-500 text-sm">Unique Users</div>
          <div className="text-3xl font-semibold">{totals?.unique_users ?? 0}</div>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-gray-500 text-sm">Route Types</div>
          <div className="text-3xl font-semibold">{(top_route_types || []).length}</div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg shadow p-4">
          <h3 className="font-semibold mb-3">Top Origins</h3>
          <ul className="space-y-2">
            {(top_origins || []).map((o, idx) => (
              <li key={idx} className="flex justify-between text-sm">
                <span>{o.origin}</span>
                <span className="text-gray-500">{o.count}</span>
              </li>
            ))}
          </ul>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <h3 className="font-semibold mb-3">Top Destinations</h3>
          <ul className="space-y-2">
            {(top_destinations || []).map((d, idx) => (
              <li key={idx} className="flex justify-between text-sm">
                <span>{d.destination}</span>
                <span className="text-gray-500">{d.count}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow p-4">
        <h3 className="font-semibold mb-3">Top Route Types</h3>
        <ul className="grid grid-cols-2 gap-2">
          {(top_route_types || []).map((rt, idx) => (
            <li key={idx} className="flex justify-between text-sm bg-gray-50 rounded px-2 py-1">
              <span>{rt.route_type}</span>
              <span className="text-gray-500">{rt.count}</span>
            </li>
          ))}
        </ul>
      </div>

      <div className="bg-white rounded-lg shadow p-4">
        <h3 className="font-semibold mb-3">Most Frequent Routes (Origin → Destination)</h3>
        <ul className="space-y-2">
          {(top_pairs || []).map((p, idx) => (
            <li key={idx} className="flex justify-between text-sm">
              <span>{p.origin} → {p.destination}</span>
              <span className="text-gray-500">{p.count}</span>
            </li>
          ))}
        </ul>
      </div>

      <div className="bg-white rounded-lg shadow p-4">
        <h3 className="font-semibold mb-3">Hourly Distribution</h3>
        <div className="grid grid-cols-6 md:grid-cols-12 gap-2 items-end">
          {(hourly_distribution || []).map((h, idx) => (
            <div key={idx} className="text-xs text-center">
              <div className="bg-blue-600 rounded" style={{ height: `${Math.max(6, (h.count || 0) * 8)}px` }}></div>
              <div className="mt-1 text-gray-600">{h.hour}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
