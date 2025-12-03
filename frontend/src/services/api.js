import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const routeService = {
  /**
   * Calculate route between origin and destination
   */
  calculateRoute: async (origin, destination, originCoords = null, destCoords = null) => {
    try {
      const response = await api.post('/route/calculate', {
        origin,
        destination,
        origin_coords: originCoords,
        dest_coords: destCoords,
      });
      return response.data;
    } catch (error) {
      throw error.response?.data || { error: 'Failed to calculate route' };
    }
  },

  /**
   * Geocode a location name to coordinates
   */
  geocodeLocation: async (location) => {
    try {
      const response = await api.post('/route/geocode', {
        location,
      });
      return response.data;
    } catch (error) {
      throw error.response?.data || { error: 'Failed to geocode location' };
    }
  },

  /**
   * Health check
   */
  healthCheck: async () => {
    try {
      const response = await api.get('/health');
      return response.data;
    } catch (error) {
      throw error.response?.data || { error: 'Service unavailable' };
    }
  },
};

export default api;
