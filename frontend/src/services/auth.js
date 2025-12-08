import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000/api';

const api = axios.create({
  baseURL: API_BASE_URL + '/auth',
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const authService = {
  register: async (username, password, role = 'user') => {
    try {
      const response = await api.post('/register', { username, password, role });
      return response.data;
    } catch (error) {
      return error.response?.data || { error: 'Registration failed' };
    }
  },
  login: async (username, password) => {
    try {
      const response = await api.post('/login', { username, password });
      return response.data;
    } catch (error) {
      return error.response?.data || { error: 'Login failed' };
    }
  },
  logout: async () => {
    try {
      const response = await api.post('/logout');
      return response.data;
    } catch (error) {
      return error.response?.data || { error: 'Logout failed' };
    }
  },
  me: async () => {
    try {
      const response = await api.get('/me');
      return response.data;
    } catch (error) {
      return error.response?.data || { error: 'Not logged in' };
    }
  },
};
