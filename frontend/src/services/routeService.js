import api from './api';

export const routeService = {
  async listCorridors() {
    const { data } = await api.get('/routes');
    return data;
  },
  async listVehicles() {
    const { data } = await api.get('/routes/vehicles');
    return data;
  },
  async listDispatchPlans() {
    const { data } = await api.get('/routes/dispatch-plans');
    return data;
  },
  async getDispatchPlan(planId) {
    const { data } = await api.get(`/routes/dispatch-plans/${planId}`);
    return data;
  },
  async generateDispatchPlan(payload) {
    const { data } = await api.post('/routes/dispatch-plans', payload);
    return data;
  },
  async updatePlanStatus(planId, status, notes = null) {
    const { data } = await api.patch(`/routes/dispatch-plans/${planId}/status`, {
      status,
      notes,
    });
    return data;
  },
  async updateStopStatus(stopId, status, notes = null, shipmentUpdates = []) {
    const { data } = await api.patch(`/routes/stops/${stopId}/status`, {
      status,
      notes,
      shipment_updates: shipmentUpdates,
    });
    return data;
  },
  async getRoadNetworkStatus() {
    const { data } = await api.get('/routes/road-network/status');
    return data;
  },
  async syncRoadNetwork(forceRefresh = false) {
    const { data } = await api.post(
      '/routes/road-network/sync',
      { force_refresh: forceRefresh },
      { timeout: 75000 }
    );
    return data;
  },
  async osmShortestPath(payload) {
    const { data } = await api.post('/routes/road-network/shortest-path', payload);
    return data;
  },
};
