import React, { useEffect, useState } from 'react';
import PageHeader from '../components/common/PageHeader';
import DataTable from '../components/tables/DataTable';
import StatusBadge from '../components/common/StatusBadge';
import ModuleActionPlaceholder from '../components/forms/ModuleActionPlaceholder';
import { hospitalService } from '../services/hospitalService';
import { formatNumber } from '../utils/formatters';

export default function Hospitals() {
  const [hospitals, setHospitals] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    hospitalService
      .list()
      .then(setHospitals)
      .catch(() => setHospitals([]))
      .finally(() => setLoading(false));
  }, []);

  const columns = [
    { key: 'code', header: 'Code' },
    { key: 'name', header: 'Hospital Profile (Synthetic)' },
    { key: 'area', header: 'Locality' },
    {
      key: 'priority_level',
      header: 'Emergency Priority',
      render: (r) => <StatusBadge status={r.priority_level} />,
    },
    {
      key: 'bed_capacity',
      header: 'Beds (Synthetic)',
      render: (r) => formatNumber(r.bed_capacity),
    },
    {
      key: 'coords',
      header: 'Coordinates',
      render: (r) => `${r.latitude.toFixed(4)}, ${r.longitude.toFixed(4)}`,
    },
  ];

  return (
    <div>
      <PageHeader
        title="Hospital Management"
        badge="Priority Tiers"
        description="Hospitals categorized into Critical, High, and Normal emergency priority tiers for lexicographic shortage optimization."
        actions={<ModuleActionPlaceholder label="+ Register Hospital (Next Sprint)" />}
      />
      <DataTable
        columns={columns}
        rows={hospitals}
        loading={loading}
        emptyMessage="No hospital profiles returned. Start backend API and seed the synthetic dataset."
      />
    </div>
  );
}
