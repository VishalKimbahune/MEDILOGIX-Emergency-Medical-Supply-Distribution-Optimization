import api from './api';

export const optimizationService = {
  async listRuns() {
    const { data } = await api.get('/optimization/runs');
    return data;
  },
  async runTransportation(payload = {}) {
    const { data } = await api.post('/optimization/transportation', {
      model_type: 'transportation_lp',
      ...payload,
    });
    return data;
  },
  async runLexicographicPriority(payload = {}) {
    const { data } = await api.post('/optimization/priority', {
      model_type: 'lexicographic_priority',
      ...payload,
    });
    return data;
  },
};
