import React from 'react';
import { Info } from 'lucide-react';

export default function PlaceholderNotice({ title, description, todos = [] }) {
  return (
    <div className="rounded-xl border border-dashed border-slate-300 bg-white p-6">
      <div className="flex items-start gap-3">
        <div className="rounded-lg bg-teal-50 p-2 text-teal-700">
          <Info className="h-5 w-5" />
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
            <span className="rounded bg-amber-50 px-2 py-0.5 text-[11px] font-semibold text-amber-800 ring-1 ring-inset ring-amber-600/20">
              UI Shell / Planned Module
            </span>
          </div>
          <p className="mt-1 text-sm text-slate-600">{description}</p>
          {todos.length > 0 && (
            <ul className="mt-3 list-disc space-y-1 pl-5 text-xs text-slate-600">
              {todos.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
