import axios from 'axios';

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json',
  },
});

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

export async function fetchRoutes() {
  const { data } = await api.get('/routes');
  return data;
}

export async function fetchScenarios() {
  const { data } = await api.get('/scenarios');
  return data;
}

export default api;
