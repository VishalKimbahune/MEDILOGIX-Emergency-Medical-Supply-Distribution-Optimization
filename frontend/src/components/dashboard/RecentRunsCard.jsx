import React from 'react';
import { Link } from 'react-router-dom';
import StatusBadge from '../common/StatusBadge';
import { formatCurrencyINR, formatNumber, formatPercent } from '../../utils/formatters';

export default function RecentRunsCard({ runs = [] }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex items-center justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold text-slate-900">
            Recent Optimization Runs
          </h2>
          <p className="text-xs text-slate-500">
            Persisted PuLP solver executions from /api/optimization/runs
          </p>
        </div>
        <Link
          to="/optimization"
          className="rounded-lg border border-teal-200 bg-teal-50 px-2.5 py-1 text-xs font-semibold text-teal-800 hover:bg-teal-100"
        >
          Open Optimizer
        </Link>
      </div>

      {runs.length === 0 ? (
        <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-4 py-6 text-center text-xs text-slate-500">
          No optimization runs recorded yet. Visit the <strong>Optimization</strong> page to execute
          a Transportation LP or Lexicographic Priority run.
        </div>
      ) : (
        <div className="divide-y divide-slate-100">
          {runs.slice(0, 5).map((run) => {
            const totalDemand = run.total_allocated + run.total_unmet_demand;
            const fulfillmentPct =
              totalDemand > 0 ? (run.total_allocated / totalDemand) * 100 : 100;
            return (
              <div key={run.id} className="py-3 text-xs">
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <p className="font-semibold text-slate-900">{run.run_code}</p>
                    <p className="text-[11px] text-slate-500">
                      {run.model_type === 'lexicographic_priority'
                        ? 'Lexicographic Priority (4-Stage)'
                        : 'Transportation LP'}
                    </p>
                  </div>
                  <StatusBadge status={run.solver_status} />
                </div>
                <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-slate-600">
                  <span>
                    Fulfilled: <strong className="text-emerald-700">{formatPercent(fulfillmentPct)}</strong>
                  </span>
                  <span>
                    Alloc/Unmet: <strong>{formatNumber(run.total_allocated)}</strong> /{' '}
                    <strong>{formatNumber(run.total_unmet_demand)}</strong>
                  </span>
                  <span>
                    Cost: <strong className="text-slate-900">{formatCurrencyINR(run.total_cost)}</strong>
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
