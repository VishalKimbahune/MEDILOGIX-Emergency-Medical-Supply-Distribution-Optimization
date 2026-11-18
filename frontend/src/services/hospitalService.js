import api from './api';

export const hospitalService = {
  async list(filters = {}) {
    const params =
      typeof filters === 'string'
        ? { priority_level: filters }
        : Object.fromEntries(
            Object.entries(filters || {}).filter(([, v]) => v !== null && v !== undefined && v !== '')
          );
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
