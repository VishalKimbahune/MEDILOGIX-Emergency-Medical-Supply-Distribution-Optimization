import api from './api';

export async function fetchHospitalDashboard() {
  const { data } = await api.get('/hospital/dashboard');
  return data;
}

export async function fetchHospitalProfile() {
  const { data } = await api.get('/hospital/profile');
  return data;
}

export async function updateHospitalProfile(payload) {
  const { data } = await api.patch('/hospital/profile', payload);
  return data;
}

export async function fetchHospitalProducts() {
  const { data } = await api.get('/hospital/products');
  return data;
}

export async function fetchHospitalOrders(params = {}) {
  const { data } = await api.get('/hospital/orders', { params });
  return data;
}

export async function fetchHospitalOrderDetail(demandId) {
  const { data } = await api.get(`/hospital/orders/${demandId}`);
  return data;
}

export async function createHospitalOrder(payload) {
  const { data } = await api.post('/hospital/orders', payload);
  return data;
}
