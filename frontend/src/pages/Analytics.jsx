import React, { useEffect, useState } from 'react';
import PageHeader from '../components/common/PageHeader';
import SupplyDemandChart from '../components/charts/SupplyDemandChart';
import DataTable from '../components/tables/DataTable';
import StatusBadge from '../components/common/StatusBadge';
import { fetchSupplyDemandGap } from '../services/api';
import { formatNumber } from '../utils/formatters';

export default function Analytics() {
  const [gapData, setGapData] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchSupplyDemandGap()
      .then(setGapData)
      .catch(() => setGapData([]))
      .finally(() => setLoading(false));
  }, []);

  const columns = [
    { key: 'product_code', header: 'Code' },
    { key: 'product_name', header: 'Medical Product' },
    { key: 'total_supply', header: 'Available Supply', render: (r) => formatNumber(r.total_supply) },
    {
      key: 'total_open_demand',
      header: 'Open Demand',
      render: (r) => formatNumber(r.total_open_demand),
    },
    {
      key: 'net_balance',
      header: 'Net Balance',
      render: (r) => `${r.net_balance >= 0 ? '+' : ''}${formatNumber(r.net_balance)}`,
    },
    {
      key: 'shortage_flag',
      header: 'Balance Status',
      render: (r) => (
        <StatusBadge
          status={r.shortage_flag ? 'shortage' : 'adequate'}
          label={r.shortage_flag ? 'Controlled Shortage' : 'Adequate'}
        />
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Performance Analytics & Reports"
        badge="Live Supply-Demand Gap"
        description="Product-wise supply coverage, controlled shortage detection, and optimization performance metrics."
      />
      <SupplyDemandChart data={gapData} />
      <DataTable
        columns={columns}
        rows={gapData}
        loading={loading}
        emptyMessage="No analytics data available. Start backend API and seed the synthetic dataset."
      />
    </div>
  );
}
