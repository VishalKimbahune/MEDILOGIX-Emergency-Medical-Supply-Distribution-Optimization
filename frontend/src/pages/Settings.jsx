import React from 'react';
import PageHeader from '../components/common/PageHeader';
import PlaceholderNotice from '../components/common/PlaceholderNotice';
import { useApiHealth } from '../hooks/useApiHealth';

export default function Settings() {
  const { health, status } = useApiHealth();

  return (
    <div className="space-y-6">
      <PageHeader
        title="Platform Settings & Geographical Scope"
        badge="Configuration"
        description="Environment-driven API connectivity and configurable geographical boundaries (expandable from Pune Urban to full Pune District)."
      />

      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-sm font-semibold text-slate-900">Runtime Environment Status</h2>
        <dl className="mt-4 grid grid-cols-1 gap-4 text-xs sm:grid-cols-2">
          <div className="rounded-lg bg-slate-50 p-3">
            <dt className="font-semibold text-slate-500">API Base URL</dt>
            <dd className="mt-1 font-mono text-slate-900">
              {import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api'}
            </dd>
          </div>
          <div className="rounded-lg bg-slate-50 p-3">
            <dt className="font-semibold text-slate-500">Backend Connectivity</dt>
            <dd className="mt-1 font-semibold capitalize text-slate-900">{status}</dd>
          </div>
          <div className="rounded-lg bg-slate-50 p-3">
            <dt className="font-semibold text-slate-500">Configured Region</dt>
            <dd className="mt-1 text-slate-900">
              {health?.geographical_scope?.region_name || 'Pune Urban & Pimpri-Chinchwad'}
            </dd>
          </div>
          <div className="rounded-lg bg-slate-50 p-3">
            <dt className="font-semibold text-slate-500">Database Connected</dt>
            <dd className="mt-1 text-slate-900">
              {health ? (health.database_connected ? 'Yes' : 'No') : 'Unknown (API offline)'}
            </dd>
          </div>
        </dl>
      </div>

      <PlaceholderNotice
        title="Configurable Solver Parameters & Region Expansion"
        description="Geographical bounds are controlled via backend environment variables (GEO_MIN_LAT, GEO_MAX_LAT, GEO_MIN_LON, GEO_MAX_LON) for future expansion to the entire Pune district."
        todos={[
          'Add configurable solver tolerances and batch rounding options',
          'Add CSV import/export trigger for academic demonstrations',
        ]}
      />
    </div>
  );
}
