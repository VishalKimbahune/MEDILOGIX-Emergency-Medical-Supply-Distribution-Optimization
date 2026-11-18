import React from 'react';

export default function ModuleActionPlaceholder({ label = 'Create Record (Planned)' }) {
  return (
    <button
      type="button"
      disabled
      title="Interactive form drawer will be enabled in the next development phase"
      className="cursor-not-allowed rounded-lg border border-slate-200 bg-slate-100 px-3.5 py-2 text-xs font-semibold text-slate-500"
    >
      {label}
    </button>
  );
}
