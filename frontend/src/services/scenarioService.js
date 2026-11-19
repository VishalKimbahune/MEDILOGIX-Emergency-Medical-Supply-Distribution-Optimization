import api from './api';

export const scenarioService = {
  async listScenarios() {
    const { data } = await api.get('/scenarios');
    return data;
  },
  async listSimulationRuns() {
    const { data } = await api.get('/scenarios/runs');
    return data;
  },
  async getSimulationRun(simulationId) {
    const { data } = await api.get(`/scenarios/runs/${simulationId}`);
    return data;
  },
  async runSimulation(payload) {
    const { data } = await api.post('/scenarios/simulate', payload);
    return data;
  },
};
