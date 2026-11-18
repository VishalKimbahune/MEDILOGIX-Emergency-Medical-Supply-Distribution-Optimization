import React, { useEffect, useState } from 'react';
import PageHeader from '../components/common/PageHeader';
import DataTable from '../components/tables/DataTable';
import StatusBadge from '../components/common/StatusBadge';
import ModuleActionPlaceholder from '../components/forms/ModuleActionPlaceholder';
import { demandService } from '../services/demandService';
import { formatNumber } from '../utils/formatters';

export default function Demands() {
  const [demands, setDemands] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    demandService
      .list()
      .then(setDemands)
      .catch(() => setDemands([]))
      .finally(() => setLoading(false));
  }, []);

  const columns = [
    { key: 'demand_code', header: 'Demand Code' },
    { key: 'hospital_id', header: 'Hospital ID' },
    { key: 'product_id', header: 'Product ID' },
    {
      key: 'quantity_requested',
      header: 'Requested Qty',
      render: (r) => formatNumber(r.quantity_requested),
    },
    {
      key: 'priority_level',
      header: 'Priority',
      render: (r) => <StatusBadge status={r.priority_level} />,
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
        title="Hospital Demand Requests"
        badge="Synthetic Demand"
        description="Open hospital supply requests driving multi-commodity transportation and lexicographic shortage solvers."
        actions={<ModuleActionPlaceholder label="+ New Demand Request (Next Sprint)" />}
      />
      <DataTable
        columns={columns}
        rows={demands}
        loading={loading}
        emptyMessage="No demand requests loaded from /api/demands."
      />
    </div>
  );
}
