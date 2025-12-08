import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000/api';

const api = axios.create({
  baseURL: API_BASE_URL + '/admin',
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
});

export const adminService = {
  stats: async () => {
    try {
      const res = await api.get('/stats');
      return res.data;
    } catch (error) {
      return error.response?.data || { error: 'Failed to load stats' };
    }
  },
};
