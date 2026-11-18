import React, { useEffect, useState } from 'react';
import PageHeader from '../components/common/PageHeader';
import PlaceholderNotice from '../components/common/PlaceholderNotice';
import DataTable from '../components/tables/DataTable';
import { fetchScenarios } from '../services/api';

export default function Scenarios() {
  const [scenarios, setScenarios] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchScenarios()
      .then(setScenarios)
      .catch(() => setScenarios([]))
      .finally(() => setLoading(false));
  }, []);

  const columns = [
    { key: 'id', header: 'ID' },
    { key: 'name', header: 'Scenario Name' },
    { key: 'scenario_type', header: 'Disruption Type' },
    { key: 'description', header: 'Description' },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Disaster Scenario Simulator"
        badge="Resilience Testing"
        description="Simulate warehouse outages, road corridor closures, and emergency hospital demand surges to measure supply-chain resilience."
      />
      <PlaceholderNotice
        title="Interactive Disaster Scenario Workbench"
        description="The backend perturbation engine (backend/app/simulation/scenario_engine.py) and /api/scenarios CRUD routes are initialized. Interactive scenario builder and baseline-vs-disrupted comparison views are scheduled for the next sprint."
        todos={[
          'Warehouse outage toggle (e.g., disable Swargate Central Emergency Depot WH-02)',
          'Monsoon road-closure selector on Pune arterial corridors',
          'Side-by-side baseline vs. disrupted cost & critical-shortage delta report',
        ]}
      />
      <DataTable
        columns={columns}
        rows={scenarios}
        loading={loading}
        emptyMessage="No saved disaster scenarios yet."
      />
    </div>
  );
}
