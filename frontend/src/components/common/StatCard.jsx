import React from 'react';

const ACCENT_STYLES = {
  teal: 'bg-teal-50 text-teal-700 border-teal-100',
  red: 'bg-red-50 text-red-700 border-red-100',
  orange: 'bg-orange-50 text-orange-700 border-orange-100',
  emerald: 'bg-emerald-50 text-emerald-700 border-emerald-100',
  slate: 'bg-slate-100 text-slate-700 border-slate-200',
};

export default function StatCard({
  title,
  value,
  subtitle,
  icon: Icon,
  accent = 'teal',
  sourceTag = 'Live API',
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition hover:border-slate-300">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
            {title}
          </p>
          <p className="mt-2 text-2xl font-bold tracking-tight text-slate-900">
            {value}
          </p>
        </div>
        {Icon && (
          <div
            className={`flex h-10 w-10 items-center justify-center rounded-lg border ${
              ACCENT_STYLES[accent] || ACCENT_STYLES.teal
            }`}
          >
            <Icon className="h-5 w-5" />
          </div>
        )}
      </div>
      <div className="mt-3 flex items-center justify-between gap-2 text-xs text-slate-500">
        <span className="truncate">{subtitle}</span>
        <span className="shrink-0 rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium text-slate-600">
          {sourceTag}
        </span>
      </div>
    </div>
  );
}
