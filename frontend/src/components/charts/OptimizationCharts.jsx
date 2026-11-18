import React from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

const PRIORITY_COLORS = {
  critical: '#dc2626',
  high: '#f97316',
  normal: '#059669',
};

function ChartCard({ title, subtitle, children }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-4">
        <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
        {subtitle && <p className="mt-0.5 text-xs text-slate-500">{subtitle}</p>}
      </div>
      <div className="h-64 w-full">{children}</div>
    </div>
  );
}

export default function OptimizationCharts({ result }) {
  if (!result) return null;

  const productData = result.product_summary || [];
  const priorityData = (result.priority_summary || []).map((item) => ({
    ...item,
    tierLabel:
      item.priority_level.charAt(0).toUpperCase() + item.priority_level.slice(1),
  }));
  const warehouseData = result.warehouse_utilization || [];

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
      {/* 1. Supply vs. Demand by Product */}
      <ChartCard
        title="Supply vs. Demand by Product"
        subtitle="Available warehouse stock compared against open hospital demand."
      >
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={productData} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey="product_name" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Bar dataKey="total_supply" name="Available Supply" fill="#0d9488" radius={[4, 4, 0, 0]} />
            <Bar dataKey="total_demand" name="Total Demand" fill="#f97316" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>

      {/* 2. Allocated vs. Unmet Demand by Product */}
      <ChartCard
        title="Allocated vs. Unmet Demand by Product"
        subtitle="Planned allocations x[i,j,k] versus unmet shortage u[j,k]."
      >
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={productData} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey="product_name" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Bar dataKey="total_allocated" name="Allocated Units" stackId="a" fill="#059669" />
            <Bar dataKey="total_unmet" name="Unmet Units" stackId="a" fill="#dc2626" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>

      {/* 3. Priority-Wise Fulfillment (%) */}
      <ChartCard
        title="Priority-Wise Demand Fulfillment (%)"
        subtitle="Percentage of hospital demand satisfied across Critical, High, and Normal tiers."
      >
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={priorityData} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey="tierLabel" tick={{ fontSize: 11 }} />
            <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} unit="%" />
            <Tooltip formatter={(val) => [`${Number(val).toFixed(2)}%`, 'Fulfillment']} />
            <Bar dataKey="fulfillment_pct" name="Fulfillment %" radius={[4, 4, 0, 0]}>
              {priorityData.map((entry) => (
                <Cell
                  key={entry.priority_level}
                  fill={PRIORITY_COLORS[entry.priority_level] || '#0d9488'}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>

      {/* 4. Warehouse Planned Stock Utilization */}
      <ChartCard
        title="Warehouse Utilization (%)"
        subtitle="Planned outbound allocation share of each warehouse's available stock."
      >
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={warehouseData} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey="warehouse_code" tick={{ fontSize: 11 }} />
            <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} unit="%" />
            <Tooltip formatter={(val) => [`${Number(val).toFixed(2)}%`, 'Utilization']} />
            <Bar dataKey="utilization_pct" name="Utilization %" fill="#0f766e" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>

      {/* 5. Transportation Cost Distribution */}
      <div className="lg:col-span-2">
        <ChartCard
          title="Transportation Cost Distribution by Product (INR)"
          subtitle="Optimal shipping expenditure broken down across essential medical commodities."
        >
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={productData} margin={{ top: 8, right: 16, left: 8, bottom: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="product_name" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip formatter={(val) => [`₹${Number(val).toLocaleString('en-IN')}`, 'Transport Cost']} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Bar dataKey="transport_cost" name="Transport Cost (INR)" fill="#132240" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>
    </div>
  );
}
