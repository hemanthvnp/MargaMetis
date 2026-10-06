import api from './http';

const get = async (path, params, fallback) => {
  try {
    const res = await api.get(path, { params });
    return res.data;
  } catch (error) {
    return error.response?.data || { error: fallback };
  }
};

export const spatialService = {
  nearby: params => get('/spatial/nearby', params, 'Failed to load nearby places'),
  adjacentRoads: params => get('/spatial/adjacent-roads', params, 'Failed to load adjacent roads'),
  summary: params => get('/spatial/summary', params, 'Failed to load area summary'),
  alongRoute: params => get('/spatial/along-route', params, 'Failed to find places along the route'),
  withinArea: params => get('/spatial/within-area', params, 'Failed to find places in the area'),
  compareAreas: params => get('/spatial/compare-areas', params, 'Failed to compare the areas'),
  nearestEach: params => get('/spatial/nearest-each', params, 'Failed to find the nearest places'),
  distance: params => get('/spatial/distance', params, 'Failed to measure distance'),
};
