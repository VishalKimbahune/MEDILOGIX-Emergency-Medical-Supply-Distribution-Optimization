import React from 'react';
import { BookOpen, CheckCircle2, ShieldCheck } from 'lucide-react';
import StatusBadge from '../common/StatusBadge';
import { formatCurrencyINR, formatNumber } from '../../utils/formatters';

export default function MathematicalExplanationPanel({ result }) {
  if (!result) return null;

  const form = result.formulation_summary || {};
  const stages = result.stage_results || [];
  const isOptimal = result.solver_status === 'Optimal';

  return (
    <div className="space-y-6">
      {/* Solver & Optimality Verification Banner */}
      <div
        className={`rounded-xl border p-5 ${
          isOptimal
            ? 'border-emerald-200 bg-emerald-50/70'
            : 'border-red-200 bg-red-50/70'
        }`}
      >
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex items-start gap-3">
            <BookOpen
              className={`mt-0.5 h-5 w-5 shrink-0 ${
                isOptimal ? 'text-emerald-700' : 'text-red-700'
              }`}
            />
            <div>
              <h3 className="text-sm font-bold text-slate-900">
                {form.model_title || 'Operations Research Mathematical Formulation'}
              </h3>
              <p className="mt-1 text-xs leading-relaxed text-slate-700">
                {form.interpretation || result.notes}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <StatusBadge status={result.solver_status} />
            <span className="rounded bg-white px-2 py-0.5 text-[11px] font-semibold text-slate-700 ring-1 ring-slate-200">
              {result.solver_name}
            </span>
          </div>
        </div>
      </div>

      {/* Formulation Breakdown Grid */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <h4 className="text-xs font-bold uppercase tracking-wider text-teal-700">
            Objective Function
          </h4>
          <div className="mt-2.5 rounded-lg bg-slate-900 px-4 py-3 font-mono text-xs text-teal-300">
            {form.objective_function ||
              'Minimize transportation cost and prioritized unmet demand'}
          </div>

          <h4 className="mt-5 text-xs font-bold uppercase tracking-wider text-teal-700">
            Decision Variables
          </h4>
          <ul className="mt-2 space-y-1.5 text-xs text-slate-700">
            {(form.decision_variables || []).map((item) => (
              <li
                key={item}
                className="rounded-md bg-slate-50 px-3 py-1.5 font-mono text-[11px]"
              >
                {item}
              </li>
            ))}
          </ul>

          <div className="mt-4 grid grid-cols-3 gap-2 text-center text-xs">
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-2.5">
              <p className="text-[10px] font-semibold uppercase text-slate-500">Variables</p>
              <p className="mt-0.5 font-bold text-slate-900">
                {formatNumber(form.variable_count ?? 0)}
              </p>
            </div>
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-2.5">
              <p className="text-[10px] font-semibold uppercase text-slate-500">Constraints</p>
              <p className="mt-0.5 font-bold text-slate-900">
                {formatNumber(form.constraint_count ?? 0)}
              </p>
            </div>
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-2.5">
              <p className="text-[10px] font-semibold uppercase text-slate-500">Open Routes</p>
              <p className="mt-0.5 font-bold text-slate-900">
                {formatNumber(form.sets?.available_routes_count ?? 0)}
              </p>
            </div>
          </div>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <h4 className="text-xs font-bold uppercase tracking-wider text-teal-700">
            Mathematical Constraints
          </h4>
          <ul className="mt-2.5 space-y-2 text-xs text-slate-700">
            {(form.constraints || []).map((c) => (
              <li
                key={c}
                className="flex items-start gap-2 rounded-lg border border-slate-100 bg-slate-50 px-3 py-2 font-mono text-[11px]"
              >
                <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-teal-600" />
                <span>{c}</span>
              </li>
            ))}
          </ul>

          <h4 className="mt-5 text-xs font-bold uppercase tracking-wider text-teal-700">
            Priority Execution Sequence
          </h4>
          <ol className="mt-2 space-y-1.5 text-xs text-slate-700">
            {(form.priority_sequence || []).map((step) => (
              <li key={step} className="rounded-md bg-slate-50 px-3 py-1.5">
                {step}
              </li>
            ))}
          </ol>
        </div>
      </div>

      {/* Sequential Solver Stages Table */}
      {stages.length > 0 && (
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <div className="border-b border-slate-200 px-5 py-3.5">
            <h4 className="text-sm font-semibold text-slate-900">
              Stage-Wise Optimal Objective Values &amp; Solver Progression
            </h4>
            <p className="text-xs text-slate-500">
              Each stage preserves all prior optimal priority objectives within numerical tolerance (10⁻⁸).
            </p>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-left text-xs">
              <thead className="bg-slate-50 text-[11px] font-semibold uppercase text-slate-500">
                <tr>
                  <th className="px-4 py-2.5">Stage</th>
                  <th className="px-4 py-2.5">Optimization Objective</th>
                  <th className="px-4 py-2.5">Tier</th>
                  <th className="px-4 py-2.5">Optimal Value</th>
                  <th className="px-4 py-2.5">Status</th>
                  <th className="px-4 py-2.5">Time (ms)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {stages.map((st) => (
                  <tr key={st.stage}>
                    <td className="px-4 py-3 font-bold text-slate-900">#{st.stage}</td>
                    <td className="px-4 py-3 font-medium text-slate-800">{st.name}</td>
                    <td className="px-4 py-3">
                      <StatusBadge status={st.priority_tier} />
                    </td>
                    <td className="px-4 py-3 font-mono font-semibold text-slate-900">
                      {st.objective_value === null || st.objective_value === undefined
                        ? '—'
                        : st.objective_metric === 'total_transport_cost_inr'
                        ? formatCurrencyINR(st.objective_value)
                        : st.objective_metric.endsWith('_unmet_fraction')
                        ? `${(st.objective_value * 100).toFixed(2)}% unmet (${st.objective_value})`
                        : formatNumber(st.objective_value)}
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge
                        status={st.skipped ? 'inactive' : st.solver_status}
                        label={st.solver_status}
                      />
                    </td>
                    <td className="px-4 py-3 text-slate-600">{st.execution_time_ms} ms</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Data Integrity Guarantee Note */}
      <div className="flex items-start gap-2.5 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-xs text-slate-600">
        <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-teal-700" />
        <p>
          <strong>Data Integrity &amp; Planned Allocation Separation:</strong> Executing an optimization
          run persists immutable planned allocations linked to <code>{result.run_code}</code> without
          modifying warehouse inventory stock or hospital demand requests.
        </p>
      </div>
    </div>
  );
}
