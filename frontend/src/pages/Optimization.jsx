import React, { useState } from 'react';
import { Play } from 'lucide-react';
import PageHeader from '../components/common/PageHeader';
import StatusBadge from '../components/common/StatusBadge';
import DataTable from '../components/tables/DataTable';
import { optimizationService } from '../services/optimizationService';
import { formatCurrencyINR, formatNumber, formatPercent } from '../utils/formatters';

export default function Optimization() {
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  async function handleRun(mode) {
    setRunning(true);
    setError(null);
    try {
      const data =
        mode === 'priority'
          ? await optimizationService.runLexicographicPriority()
          : await optimizationService.runTransportation();
      setResult(data);
    } catch (err) {
      setError(
        err?.response?.data?.detail ||
          'Failed to execute optimization solver. Verify backend API is running and seeded.'
      );
    } finally {
      setRunning(false);
    }
  }

  const allocationColumns = [
    { key: 'warehouse_code', header: 'Warehouse' },
    { key: 'hospital_code', header: 'Hospital' },
    { key: 'product_code', header: 'Product' },
    {
      key: 'quantity_allocated',
      header: 'Allocated Qty (x[i,j,k])',
      render: (r) => formatNumber(r.quantity_allocated),
    },
    {
      key: 'unit_cost',
      header: 'Unit Cost',
      render: (r) => formatCurrencyINR(r.unit_cost),
    },
    {
      key: 'transport_cost',
      header: 'Total Cost',
      render: (r) => formatCurrencyINR(r.transport_cost),
    },
  ];

  return (
    <div>
      <PageHeader
        title="Operations Research Optimization"
        badge="PuLP CBC Solver"
        description="Execute live Multi-Commodity Transportation LP or 4-Stage Lexicographic Priority Shortage Optimization."
        actions={
          <>
            <button
              type="button"
              disabled={running}
              onClick={() => handleRun('transportation')}
              className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50"
            >
              <Play className="h-3.5 w-3.5" />
              Run Transportation LP
            </button>
            <button
              type="button"
              disabled={running}
              onClick={() => handleRun('priority')}
              className="inline-flex items-center gap-2 rounded-lg bg-teal-600 px-4 py-2 text-xs font-semibold text-white hover:bg-teal-700 disabled:opacity-50"
            >
              <Play className="h-3.5 w-3.5" />
              Run Lexicographic Priority
            </button>
          </>
        }
      />

      {error && (
        <div className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-xs text-red-800">
          {error}
        </div>
      )}

      {!result ? (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white p-8 text-center">
          <h3 className="text-sm font-semibold text-slate-900">
            Ready to Compute Optimal Supply Allocation
          </h3>
          <p className="mx-auto mt-2 max-w-xl text-xs text-slate-600">
            All allocations are computed dynamically by PuLP (CBC) using live warehouse stock,
            open hospital demand, priority tiers, and corridor availability—never hardcoded.
          </p>
        </div>
      ) : (
        <div className="space-y-6">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <p className="text-xs font-semibold uppercase text-slate-500">Solver Status</p>
              <div className="mt-2 flex items-center gap-2">
                <StatusBadge status={result.solver_status} />
                <span className="text-xs text-slate-500">{result.execution_time_ms} ms</span>
              </div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <p className="text-xs font-semibold uppercase text-slate-500">Total Transport Cost</p>
              <p className="mt-2 text-xl font-bold text-slate-900">
                {formatCurrencyINR(result.total_cost)}
              </p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <p className="text-xs font-semibold uppercase text-slate-500">Allocated / Unmet</p>
              <p className="mt-2 text-xl font-bold text-slate-900">
                {formatNumber(result.total_allocated)} / {formatNumber(result.total_unmet_demand)}
              </p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <p className="text-xs font-semibold uppercase text-slate-500">Tier Unmet Fractions</p>
              <p className="mt-2 text-xs text-slate-700">
                Crit: <strong>{formatPercent((result.tier_unmet_fractions.critical || 0) * 100)}</strong>{' '}
                | High: <strong>{formatPercent((result.tier_unmet_fractions.high || 0) * 100)}</strong>{' '}
                | Norm: <strong>{formatPercent((result.tier_unmet_fractions.normal || 0) * 100)}</strong>
              </p>
            </div>
          </div>

          <DataTable
            columns={allocationColumns}
            rows={result.allocations}
            emptyMessage="No non-zero allocations returned."
          />
        </div>
      )}
    </div>
  );
}
