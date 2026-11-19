import axios from 'axios';

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api';

// In-memory short-lived access token (never persisted to localStorage)
let inMemoryAccessToken = null;
let onAuthFailureCallback = null;

export function setAccessToken(token) {
  inMemoryAccessToken = token || null;
}

export function getAccessToken() {
  return inMemoryAccessToken;
}

export function clearAccessToken() {
  inMemoryAccessToken = null;
}

export function registerAuthFailureHandler(handler) {
  onAuthFailureCallback = handler;
}

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 20000,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use((config) => {
  if (inMemoryAccessToken && !config.headers?.Authorization) {
    config.headers = config.headers || {};
    config.headers.Authorization = `Bearer ${inMemoryAccessToken}`;
  }
  return config;
});

let isRefreshing = false;
let pendingQueue = [];

function resolveQueue(error, token = null) {
  pendingQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token);
    }
  });
  pendingQueue = [];
}

const AUTH_SKIP_REFRESH_PATHS = [
  '/auth/login',
  '/auth/register',
  '/auth/refresh',
  '/auth/logout',
  '/auth/forgot-password',
  '/auth/reset-password',
  '/auth/verify-email',
  '/auth/public-organizations',
];

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error?.config;
    const status = error?.response?.status;
    const reqUrl = originalRequest?.url || '';
    const isAuthRoute = AUTH_SKIP_REFRESH_PATHS.some((p) => reqUrl.includes(p));

    if (status === 401 && originalRequest && !originalRequest._retry && !isAuthRoute) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          pendingQueue.push({ resolve, reject });
        }).then((newToken) => {
          originalRequest.headers = originalRequest.headers || {};
          originalRequest.headers.Authorization = `Bearer ${newToken}`;
          return api(originalRequest);
        });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        const refreshResp = await axios.post(
          `${API_BASE_URL}/auth/refresh`,
          {},
          {
            withCredentials: true,
            headers: {
              'Content-Type': 'application/json',
              'X-Requested-With': 'XMLHttpRequest',
            },
          }
        );
        const newToken = refreshResp.data?.access_token;
        if (!newToken) {
          throw new Error('Refresh response missing access token');
        }
        setAccessToken(newToken);
        resolveQueue(null, newToken);
        originalRequest.headers = originalRequest.headers || {};
        originalRequest.headers.Authorization = `Bearer ${newToken}`;
        return api(originalRequest);
      } catch (refreshErr) {
        clearAccessToken();
        resolveQueue(refreshErr, null);
        if (typeof onAuthFailureCallback === 'function') {
          onAuthFailureCallback();
        }
        return Promise.reject(refreshErr);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  }
);

export async function fetchHealthStatus() {
  const { data } = await api.get('/health');
  return data;
}

export async function fetchAnalyticsSummary() {
  const { data } = await api.get('/analytics/summary');
  return data;
}

export async function fetchSupplyDemandGap() {
  const { data } = await api.get('/analytics/supply-demand-gap');
  return data;
}

export async function fetchAnalyticsOverview() {
  const { data } = await api.get('/analytics/overview');
  return data;
}

export async function fetchRoutes() {
  const { data } = await api.get('/routes');
  return data;
}

export async function fetchScenarios() {
  const { data } = await api.get('/scenarios');
  return data;
}

export default api;
