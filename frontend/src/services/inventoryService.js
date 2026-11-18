import api from './api';

export const inventoryService = {
  async list(filters = {}) {
    const { data } = await api.get('/inventory', { params: filters });
    return data;
  },
  async listProducts() {
    const { data } = await api.get('/products');
    return data;
  },
  async create(payload) {
    const { data } = await api.post('/inventory', payload);
    return data;
  },
  async update(id, payload) {
    const { data } = await api.put(`/inventory/${id}`, payload);
    return data;
  },
  async remove(id) {
    await api.delete(`/inventory/${id}`);
  },
};
