import api from './api';

export async function listUsers(params = {}) {
  const { data } = await api.get('/admin/users', { params });
  return data;
}

export async function createUser(payload) {
  const { data } = await api.post('/admin/users', payload);
  return data;
}

export async function updateUser(userId, payload) {
  const { data } = await api.patch(`/admin/users/${userId}`, payload);
  return data;
}

export async function approveUser(userId) {
  const { data } = await api.patch(`/admin/users/${userId}/approve`);
  return data;
}

export async function rejectUser(userId, reason) {
  const { data } = await api.patch(`/admin/users/${userId}/reject`, { reason });
  return data;
}

export async function toggleUserStatus(userId, isActive) {
  const { data } = await api.patch(`/admin/users/${userId}/status`, { is_active: isActive });
  return data;
}

export async function initiateUserRecovery(userId) {
  const { data } = await api.post(`/admin/users/${userId}/initiate-recovery`);
  return data;
}

export async function approveHospitalOrder(demandId) {
  const { data } = await api.post(`/admin/orders/${demandId}/approve`);
  return data;
}

export async function rejectHospitalOrder(demandId, reason) {
  const { data } = await api.post(`/admin/orders/${demandId}/reject`, { reason });
  return data;
}

export async function listAdminVehicles() {
  const { data } = await api.get('/admin/vehicles');
  return data;
}

export async function createAdminVehicle(payload) {
  const { data } = await api.post('/admin/vehicles', payload);
  return data;
}

export async function updateAdminVehicle(vehicleId, payload) {
  const { data } = await api.put(`/admin/vehicles/${vehicleId}`, payload);
  return data;
}

export async function deleteAdminVehicle(vehicleId) {
  await api.delete(`/admin/vehicles/${vehicleId}`);
}

export async function assignDriverToAssignment(assignmentId, driverUserId) {
  const { data } = await api.patch(`/admin/assignments/${assignmentId}/driver`, {
    assigned_driver_user_id: driverUserId,
  });
  return data;
}

export async function listAuditLogs(params = {}) {
  const { data } = await api.get('/admin/audit-logs', { params });
  return data;
}
