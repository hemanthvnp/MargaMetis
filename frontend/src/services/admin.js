import api from './http';

export const adminService = {
  stats: async () => {
    try {
      const res = await api.get('/admin/stats');
      return res.data;
    } catch (error) {
      return error.response?.data || { error: 'Failed to load stats' };
    }
  },
};
