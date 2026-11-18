import React from 'react';
import StatusBadge from '../common/StatusBadge';
import { formatCurrencyINR, formatNumber } from '../../utils/formatters';

export default function RecentRunsCard({ runs = [] }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-slate-900">
            Recent Optimization Runs
          </h2>
          <p className="text-xs text-slate-500">
            Persisted PuLP solver executions from /api/optimization/runs
          </p>
        </div>
        <span className="rounded bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
          {runs.length} recorded
        </span>
      </div>

      {runs.length === 0 ? (
        <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-4 py-6 text-center text-xs text-slate-500">
          No optimization runs recorded yet. Visit the <strong>Optimization</strong> page to execute
          a Transportation LP or Lexicographic Priority run.
        </div>
      ) : (
        <div className="divide-y divide-slate-100">
          {runs.slice(0, 5).map((run) => (
            <div key={run.id} className="flex flex-wrap items-center justify-between gap-2 py-3 text-xs">
              <div>
                <p className="font-semibold text-slate-900">{run.run_code}</p>
                <p className="text-slate-500">{run.model_type}</p>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-slate-600">
                  Allocated: <strong>{formatNumber(run.total_allocated)}</strong>
                </span>
                <span className="text-slate-600">
                  Unmet: <strong>{formatNumber(run.total_unmet_demand)}</strong>
                </span>
                <span className="text-slate-700">
                  Cost: <strong>{formatCurrencyINR(run.total_cost)}</strong>
                </span>
                <StatusBadge status={run.solver_status} />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
