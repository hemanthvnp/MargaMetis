import axios from 'axios';

const baseURL = import.meta.env.VITE_API_URL || 'http://localhost:5050/api';
const http = axios.create({
  baseURL,
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
});

let csrfToken = null;
let csrfTokenRequest = null;

const isMutation = config =>
  ['post', 'put', 'patch', 'delete'].includes((config.method || '').toLowerCase());

http.interceptors.request.use(async config => {
  if (isMutation(config)) {
    if (!csrfToken) {
      if (!csrfTokenRequest) {
        csrfTokenRequest = http.get('/auth/me')
          .then(response => {
            csrfToken = response.data?.csrf_token || null;
            if (!csrfToken) throw new Error('CSRF token was missing from /auth/me');
          })
          .finally(() => {
            csrfTokenRequest = null;
          });
      }
      await csrfTokenRequest;
    }
    config.headers['X-CSRFToken'] = csrfToken;
  }
  return config;
});

http.interceptors.response.use(response => {
  const path = response.config.url || '';
  if (path.endsWith('/auth/me') || path.endsWith('/auth/login') || path.endsWith('/auth/register')) {
    csrfToken = response.data?.csrf_token || csrfToken;
  } else if (path.endsWith('/auth/logout')) {
    csrfToken = null;
  }
  return response;
});

export default http;
