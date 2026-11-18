import React, { useEffect, useState } from 'react';
import PageHeader from '../components/common/PageHeader';
import DataTable from '../components/tables/DataTable';
import StatusBadge from '../components/common/StatusBadge';
import ModuleActionPlaceholder from '../components/forms/ModuleActionPlaceholder';
import { warehouseService } from '../services/warehouseService';
import { formatNumber } from '../utils/formatters';

export default function Warehouses() {
  const [warehouses, setWarehouses] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    warehouseService
      .list()
      .then(setWarehouses)
      .catch(() => setWarehouses([]))
      .finally(() => setLoading(false));
  }, []);

  const columns = [
    { key: 'code', header: 'Code' },
    { key: 'name', header: 'Warehouse Name' },
    { key: 'area', header: 'Locality' },
    { key: 'city', header: 'City' },
    {
      key: 'coords',
      header: 'Coordinates',
      render: (r) => `${r.latitude.toFixed(4)}, ${r.longitude.toFixed(4)}`,
    },
    {
      key: 'storage_capacity_units',
      header: 'Capacity (Units)',
      render: (r) => formatNumber(r.storage_capacity_units),
    },
    {
      key: 'status',
      header: 'Status',
      render: (r) => <StatusBadge status={r.status} />,
    },
  ];

  return (
    <div>
      <PageHeader
        title="Warehouse Management"
        badge="Fictional Simulation Hubs"
        description="Manage medical supply hubs across Pune and Pimpri-Chinchwad. Live rows are loaded from /api/warehouses."
        actions={<ModuleActionPlaceholder label="+ Add Warehouse (Next Sprint)" />}
      />
      <DataTable
        columns={columns}
        rows={warehouses}
        loading={loading}
        emptyMessage="No warehouses returned. Start backend API and run init_db to seed synthetic hubs."
      />
    </div>
  );
}
