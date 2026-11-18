import React from 'react';
import { GitCompare, Play } from 'lucide-react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import StatusBadge from '../common/StatusBadge';
import { formatCurrencyINR, formatNumber, formatPercent } from '../../utils/formatters';

export default function ModelComparisonPanel({
  comparison,
  onRunCompare,
  loading = false,
}) {
  if (!comparison) {
    return (
      <div className="rounded-xl border border-dashed border-slate-300 bg-white p-8 text-center">
        <GitCompare className="mx-auto h-8 w-8 text-teal-600" />
        <h3 className="mt-3 text-sm font-bold text-slate-900">
          Compare Transportation Cost LP vs. Lexicographic Priority Optimization
        </h3>
        <p className="mx-auto mt-1.5 max-w-xl text-xs text-slate-600">
          Run both Operations Research models on the exact same selected network dataset to measure
          the exact trade-off between minimum shipping cost and emergency hospital priority protection.
        </p>
        <button
          type="button"
          disabled={loading}
          onClick={onRunCompare}
          className="mt-4 inline-flex items-center gap-2 rounded-lg bg-teal-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-teal-700 disabled:opacity-50"
        >
          <Play className="h-3.5 w-3.5" />
          {loading ? 'Running Side-by-Side Comparison...' : 'Run Side-by-Side Comparison'}
        </button>
      </div>
    );
  }

  const { transportation, lexicographic_priority: priority, comparison_metrics: metrics } =
    comparison;
  const tierRows = metrics.tier_comparison || [];

  const chartData = tierRows.map((row) => ({
    tier: row.priority_level.charAt(0).toUpperCase() + row.priority_level.slice(1),
    'Transportation LP': row.transportation_fulfillment_pct,
    'Lexicographic Priority': row.priority_fulfillment_pct,
  }));

  return (
    <div className="space-y-6">
      {/* Academic Interpretation Banner */}
      <div className="rounded-xl border border-teal-200 bg-teal-50/70 p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="text-sm font-bold text-slate-900">
              OR Trade-Off Analysis: Cost Minimization vs. Priority Protection
            </h3>
            <p className="mt-1.5 text-xs leading-relaxed text-slate-700">
              {metrics.explanation}
            </p>
          </div>
          <button
            type="button"
            disabled={loading}
            onClick={onRunCompare}
            className="shrink-0 rounded-lg border border-teal-300 bg-white px-3 py-1.5 text-xs font-semibold text-teal-800 hover:bg-teal-50 disabled:opacity-50"
          >
            {loading ? 'Re-running...' : 'Re-run Comparison'}
          </button>
        </div>
      </div>

      {/* Side-by-Side Headline Cards */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-[11px] font-semibold uppercase text-slate-500">
            Transportation LP Cost
          </p>
          <p className="mt-1.5 text-xl font-bold text-slate-900">
            {formatCurrencyINR(transportation.total_cost)}
          </p>
          <p className="mt-1 text-xs text-slate-500">
            Run: {transportation.run_code} &bull; {formatPercent(transportation.fulfillment_percentage)} fulfilled
          </p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-[11px] font-semibold uppercase text-slate-500">
            Lexicographic Priority Cost
          </p>
          <p className="mt-1.5 text-xl font-bold text-teal-700">
            {formatCurrencyINR(priority.total_cost)}
          </p>
          <p className="mt-1 text-xs text-slate-500">
            Run: {priority.run_code} &bull; {formatPercent(priority.fulfillment_percentage)} fulfilled
          </p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-[11px] font-semibold uppercase text-slate-500">
            Priority Protection Cost Delta
          </p>
          <p
            className={`mt-1.5 text-xl font-bold ${
              metrics.cost_difference_inr > 0 ? 'text-orange-600' : 'text-emerald-700'
            }`}
          >
            {metrics.cost_difference_inr >= 0 ? '+' : ''}
            {formatCurrencyINR(metrics.cost_difference_inr)}
          </p>
          <p className="mt-1 text-xs text-slate-500">
            {metrics.cost_difference_pct >= 0 ? '+' : ''}
            {metrics.cost_difference_pct}% relative to cost-only optimum
          </p>
        </div>
      </div>

      {/* Priority Tier Comparison Chart & Table */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <h4 className="mb-3 text-sm font-semibold text-slate-900">
            Priority Tier Fulfillment Comparison (%)
          </h4>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="tier" tick={{ fontSize: 11 }} />
                <YAxis domain={[0, 100]} unit="%" tick={{ fontSize: 11 }} />
                <Tooltip formatter={(val) => `${Number(val).toFixed(2)}%`} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Bar dataKey="Transportation LP" fill="#64748b" radius={[4, 4, 0, 0]} />
                <Bar dataKey="Lexicographic Priority" fill="#0d9488" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <div className="border-b border-slate-200 px-5 py-3.5">
            <h4 className="text-sm font-semibold text-slate-900">
              Tier-by-Tier Unmet Demand Shift
            </h4>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-left text-xs">
              <thead className="bg-slate-50 text-[11px] font-semibold uppercase text-slate-500">
                <tr>
                  <th className="px-4 py-2.5">Tier</th>
                  <th className="px-4 py-2.5">Demand</th>
                  <th className="px-4 py-2.5">Transport Unmet</th>
                  <th className="px-4 py-2.5">Priority Unmet</th>
                  <th className="px-4 py-2.5">Shortage Reduced</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {tierRows.map((row) => (
                  <tr key={row.priority_level}>
                    <td className="px-4 py-3">
                      <StatusBadge status={row.priority_level} />
                    </td>
                    <td className="px-4 py-3 font-medium text-slate-700">
                      {formatNumber(row.demand)}
                    </td>
                    <td className="px-4 py-3 text-slate-700">
                      {formatNumber(row.transportation_unmet)} (
                      {formatPercent(row.transportation_fulfillment_pct)})
                    </td>
                    <td className="px-4 py-3 font-semibold text-slate-900">
                      {formatNumber(row.priority_unmet)} (
                      {formatPercent(row.priority_fulfillment_pct)})
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`font-bold ${
                          row.unmet_reduction > 0
                            ? 'text-emerald-700'
                            : row.unmet_reduction < 0
                            ? 'text-orange-600'
                            : 'text-slate-500'
                        }`}
                      >
                        {row.unmet_reduction > 0 ? `+${formatNumber(row.unmet_reduction)}` : formatNumber(row.unmet_reduction)}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
