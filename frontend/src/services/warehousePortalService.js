import api from './api';

export async function fetchWarehouseDashboard() {
  const { data } = await api.get('/warehouse/dashboard');
  return data;
}

export async function fetchWarehouseProfile() {
  const { data } = await api.get('/warehouse/profile');
  return data;
}

export async function updateWarehouseProfile(payload) {
  const { data } = await api.patch('/warehouse/profile', payload);
  return data;
}

export async function updateWarehouseStatus(payload) {
  const { data } = await api.patch('/warehouse/status', payload);
  return data;
}

export async function fetchWarehouseInventory() {
  const { data } = await api.get('/warehouse/inventory');
  return data;
}

export async function createWarehouseStock(payload) {
  const { data } = await api.post('/warehouse/inventory', payload);
  return data;
}

export async function createWarehouseMedicineAndStock(payload) {
  const { data } = await api.post('/warehouse/products-with-stock', payload);
  return data;
}

export async function adjustWarehouseStock(inventoryId, payload) {
  const { data } = await api.patch(`/warehouse/inventory/${inventoryId}`, payload);
  return data;
}

export async function fetchWarehouseProducts() {
  const { data } = await api.get('/warehouse/products');
  return data;
}

export async function fetchWarehouseStockMovements() {
  const { data } = await api.get('/warehouse/stock-movements');
  return data;
}

export async function fetchWarehouseAllocations() {
  const { data } = await api.get('/warehouse/allocations');
  return data;
}

export async function fetchWarehouseShipments() {
  const { data } = await api.get('/warehouse/shipments');
  return data;
}

export async function updateShipmentPreparation(assignmentId, payload) {
  const { data } = await api.patch(`/warehouse/shipments/${assignmentId}/preparation`, payload);
  return data;
}
