import api from './api';

export const hospitalService = {
  async list(priorityLevel = null) {
    const params = priorityLevel ? { priority_level: priorityLevel } : {};
    const { data } = await api.get('/hospitals', { params });
    return data;
  },
  async getById(id) {
    const { data } = await api.get(`/hospitals/${id}`);
    return data;
  },
  async create(payload) {
    const { data } = await api.post('/hospitals', payload);
    return data;
  },
  async update(id, payload) {
    const { data } = await api.put(`/hospitals/${id}`, payload);
    return data;
  },
  async remove(id) {
    await api.delete(`/hospitals/${id}`);
  },
};
