import React from 'react';

const BADGE_VARIANTS = {
  critical: 'bg-red-50 text-red-700 ring-red-600/20',
  high: 'bg-orange-50 text-orange-700 ring-orange-600/20',
  normal: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20',
  active: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20',
  maintenance: 'bg-orange-50 text-orange-700 ring-orange-600/20',
  open: 'bg-teal-50 text-teal-700 ring-teal-600/20',
  planned: 'bg-slate-100 text-slate-700 ring-slate-500/20',
  dispatched: 'bg-teal-50 text-teal-700 ring-teal-600/20',
  in_transit: 'bg-sky-50 text-sky-700 ring-sky-600/20',
  delivered: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20',
  partially_delivered: 'bg-orange-50 text-orange-700 ring-orange-600/20',
  partially_fulfilled: 'bg-orange-50 text-orange-700 ring-orange-600/20',
  fulfilled: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20',
  completed: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20',
  partial: 'bg-orange-50 text-orange-700 ring-orange-600/20',
  infeasible: 'bg-red-50 text-red-700 ring-red-600/20',
  cancelled: 'bg-slate-100 text-slate-600 ring-slate-500/20',
  optimal: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20',
  inactive: 'bg-slate-100 text-slate-600 ring-slate-500/20',
  shortage: 'bg-red-50 text-red-700 ring-red-600/20',
  low_stock: 'bg-red-50 text-red-700 ring-red-600/20',
  adequate: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20',
  healthy: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20',
};

export default function StatusBadge({ status, label }) {
  const key = String(status || 'normal').toLowerCase();
  const classes =
    BADGE_VARIANTS[key] || 'bg-slate-100 text-slate-700 ring-slate-500/20';
  const formattedLabel = label || String(status || '').replace(/_/g, ' ');
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold capitalize ring-1 ring-inset ${classes}`}
    >
      {formattedLabel}
    </span>
  );
}
