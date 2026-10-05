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
  spatialAnalytics: async (k = 5) => {
    try {
      const res = await api.get('/admin/spatial-analytics', { params: { k } });
      return res.data;
    } catch (error) {
      return error.response?.data || { error: 'Failed to load spatial analytics' };
    }
  },
};
