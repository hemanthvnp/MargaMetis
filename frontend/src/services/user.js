import api from './http';

export const userService = {
  history: async (page = 1, pageSize = 20) => {
    try {
      const res = await api.get(`/user/history?page=${page}&page_size=${pageSize}`);
      return res.data;
    } catch (err) {
      return err.response?.data || { error: 'Failed to load history' };
    }
  },
  historyItem: async (id) => {
    try {
      const res = await api.get(`/user/history/${id}`);
      return res.data;
    } catch (err) {
      return err.response?.data || { error: 'Failed to load item' };
    }
  },
};
