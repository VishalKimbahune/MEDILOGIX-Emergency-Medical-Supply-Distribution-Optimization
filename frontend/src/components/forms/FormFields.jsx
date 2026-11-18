import React from 'react';
import { AlertCircle } from 'lucide-react';

const baseInputClass =
  'mt-1 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm transition placeholder:text-slate-400 focus:border-teal-600 focus:outline-none focus:ring-2 focus:ring-teal-600/20 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-500';

export function TextInput({
  label,
  name,
  type = 'text',
  value,
  onChange,
  placeholder,
  error,
  hint,
  required = false,
  disabled = false,
  min,
  max,
  step,
}) {
  return (
    <div>
      <label htmlFor={name} className="block text-xs font-semibold text-slate-700">
        {label}
        {required && <span className="ml-0.5 text-red-600">*</span>}
      </label>
      <input
        id={name}
        name={name}
        type={type}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        disabled={disabled}
        min={min}
        max={max}
        step={step}
        className={`${baseInputClass} ${
          error ? 'border-red-400 focus:border-red-500 focus:ring-red-500/20' : ''
        }`}
      />
      {error ? (
        <p className="mt-1 text-xs font-medium text-red-600">{error}</p>
      ) : (
        hint && <p className="mt-1 text-[11px] text-slate-500">{hint}</p>
      )}
    </div>
  );
}

export function SelectInput({
  label,
  name,
  value,
  onChange,
  options = [],
  error,
  hint,
  required = false,
  disabled = false,
  placeholder,
}) {
  return (
    <div>
      <label htmlFor={name} className="block text-xs font-semibold text-slate-700">
        {label}
        {required && <span className="ml-0.5 text-red-600">*</span>}
      </label>
      <select
        id={name}
        name={name}
        value={value}
        onChange={onChange}
        disabled={disabled}
        className={`${baseInputClass} ${
          error ? 'border-red-400 focus:border-red-500 focus:ring-red-500/20' : ''
        }`}
      >
        {placeholder && <option value="">{placeholder}</option>}
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
      {error ? (
        <p className="mt-1 text-xs font-medium text-red-600">{error}</p>
      ) : (
        hint && <p className="mt-1 text-[11px] text-slate-500">{hint}</p>
      )}
    </div>
  );
}

export function FormErrorBanner({ message }) {
  if (!message) return null;
  return (
    <div className="mb-4 flex items-start gap-2.5 rounded-lg border border-red-200 bg-red-50 px-3.5 py-2.5 text-xs text-red-800">
      <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-red-600" />
      <span>{message}</span>
    </div>
  );
}

export function DetailField({ label, value }) {
  return (
    <div className="rounded-lg border border-slate-100 bg-slate-50/70 px-3.5 py-2.5">
      <dt className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
        {label}
      </dt>
      <dd className="mt-1 text-sm font-medium text-slate-900">{value ?? '—'}</dd>
    </div>
  );
}
