import React from 'react';
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

export default function SupplyDemandChart({ data = [] }) {
  if (!data.length) {
    return (
      <div className="flex h-64 items-center justify-center rounded-xl border border-slate-200 bg-white p-6 text-sm text-slate-500">
        Connect backend API and seed synthetic dataset to visualize supply vs. demand balance.
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-4">
        <h3 className="text-sm font-semibold text-slate-900">
          Product-Wise Available Supply vs. Open Demand (Live DB)
        </h3>
        <p className="text-xs text-slate-500">
          Highlights controlled emergency shortages for Operations Research allocation.
        </p>
      </div>
      <div className="h-72 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey="product_name" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip />
            <Legend />
            <Bar dataKey="total_supply" name="Available Supply" fill="#0d9488" radius={[4, 4, 0, 0]} />
            <Bar dataKey="total_open_demand" name="Open Demand" fill="#f97316" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
