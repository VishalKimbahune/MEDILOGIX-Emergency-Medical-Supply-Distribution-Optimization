import api from './api';

export const warehouseService = {
  async list() {
    const { data } = await api.get('/warehouses');
    return data;
  },
  async getById(id) {
    const { data } = await api.get(`/warehouses/${id}`);
    return data;
  },
  async create(payload) {
    const { data } = await api.post('/warehouses', payload);
    return data;
  },
  async update(id, payload) {
    const { data } = await api.put(`/warehouses/${id}`, payload);
    return data;
  },
  async remove(id) {
    await api.delete(`/warehouses/${id}`);
  },
};
