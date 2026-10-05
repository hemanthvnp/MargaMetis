import api from './http';

export const authService = {
  register: async (username, password) => {
    try {
      const res = await api.post('/auth/register', { username, password });
      return res.data;
    } catch (err) {
      return err.response?.data || { error: 'Registration failed' };
    }
  },
  login: async (username, password) => {
    try {
      const res = await api.post('/auth/login', { username, password });
      return res.data;
    } catch (err) {
      return err.response?.data || { error: 'Invalid credentials' };
    }
  },
  logout: async () => {
    try {
      const res = await api.post('/auth/logout');
      return res.data;
    } catch (err) {
      return { success: false };
    }
  },
  me: async () => {
    try {
      const res = await api.get('/auth/me');
      return res.data;
    } catch {
      return { logged_in: false };
    }
  },
};
