import api from './api';

export async function fetchDeliveryDashboard() {
  const { data } = await api.get('/delivery/dashboard');
  return data;
}

export async function fetchDeliveryAssignments() {
  const { data } = await api.get('/delivery/assignments');
  return data;
}

export async function fetchDeliveryAssignmentDetail(assignmentId) {
  const { data } = await api.get(`/delivery/assignments/${assignmentId}`);
  return data;
}

export async function updateDeliveryStopStatus(stopId, payload) {
  const { data } = await api.patch(`/delivery/stops/${stopId}/status`, payload);
  return data;
}

export async function confirmDeliveryStop(stopId, payload) {
  const { data } = await api.post(`/delivery/stops/${stopId}/confirmation`, payload);
  return data;
}
