import api from './api';

export const demandService = {
  async list(filters = {}) {
    const { data } = await api.get('/demands', { params: filters });
    return data;
  },
  async create(payload) {
    const { data } = await api.post('/demands', payload);
    return data;
  },
  async update(id, payload) {
    const { data } = await api.put(`/demands/${id}`, payload);
    return data;
  },
  async remove(id) {
    await api.delete(`/demands/${id}`);
  },
};
