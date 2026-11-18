import React, { useEffect, useState } from 'react';
import PageHeader from '../components/common/PageHeader';
import DataTable from '../components/tables/DataTable';
import StatusBadge from '../components/common/StatusBadge';
import PlaceholderNotice from '../components/common/PlaceholderNotice';
import { fetchRoutes } from '../services/api';
import { formatCurrencyINR } from '../utils/formatters';

export default function RoutesPage() {
  const [routes, setRoutes] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchRoutes()
      .then(setRoutes)
      .catch(() => setRoutes([]))
      .finally(() => setLoading(false));
  }, []);

  const columns = [
    { key: 'route_code', header: 'Route ID' },
    { key: 'warehouse_code', header: 'From Warehouse' },
    { key: 'hospital_code', header: 'To Hospital' },
    {
      key: 'distance_km',
      header: 'Est. Distance (km)',
      render: (r) => `${Number(r.distance_km).toFixed(2)} km`,
    },
    {
      key: 'estimated_travel_time_min',
      header: 'Synthetic Time (min)',
      render: (r) => `${Number(r.estimated_travel_time_min).toFixed(1)} min`,
    },
    {
      key: 'base_transport_cost_per_unit',
      header: 'Base Unit Cost',
      render: (r) => formatCurrencyINR(r.base_transport_cost_per_unit),
    },
    {
      key: 'is_available',
      header: 'Corridor',
      render: (r) => (
        <StatusBadge
          status={r.is_available ? 'active' : 'critical'}
          label={r.is_available ? 'Open' : 'Closed'}
        />
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Delivery Routes & Graph Routing"
        badge="NetworkX & OR-Tools"
        description="Synthetic Pune corridor matrix (24 pairs). Travel times are analytical estimates and do NOT represent live traffic."
      />
      <DataTable
        columns={columns}
        rows={routes}
        loading={loading}
        emptyMessage="No route corridors returned from /api/routes."
      />
      <PlaceholderNotice
        title="Capacitated Vehicle Routing (OR-Tools) & OpenStreetMap Road Polylines"
        description="Allocation optimization and vehicle routing are strictly decoupled. Shortest-path Dijkstra is wired at POST /api/routes/shortest-path; multi-stop CVRP UI will be added next."
        todos={[
          'Ingest real Pune / PCMC road network via Overpass API into NetworkX',
          'Complete Google OR-Tools Capacitated VRP in backend/app/optimization/vehicle_routing.py',
          'Render dispatched multi-stop polylines on the interactive Leaflet map',
        ]}
      />
    </div>
  );
}
