import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000/api';

const api = axios.create({
  baseURL: API_BASE_URL + '/user',
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
});

export const userService = {
  history: async (page = 1, pageSize = 20) => {
    try {
      const res = await api.get(`/history?page=${page}&page_size=${pageSize}`);
      return res.data;
    } catch (error) {
      return error.response?.data || { error: 'Failed to load history' };
    }
  },
  historyItem: async (id) => {
    try {
      const res = await api.get(`/history/${id}`);
      return res.data;
    } catch (error) {
      return error.response?.data || { error: 'Failed to load history item' };
    }
  },
  queryCached: async ({ origin, destination, route_type, vehicle_type }) => {
    try {
      const params = new URLSearchParams({ origin, destination });
      if (route_type) params.set('route_type', route_type);
      if (vehicle_type) params.set('vehicle_type', vehicle_type);
      const res = await api.get(`/history/query?${params.toString()}`);
      return res.data;
    } catch (error) {
      return error.response?.data || { error: 'No cached result' };
    }
  },
};
