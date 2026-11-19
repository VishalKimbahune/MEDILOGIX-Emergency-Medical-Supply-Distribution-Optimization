import React, { useCallback, useEffect, useState } from 'react';
import {
  Activity,
  AlertTriangle,
  BarChart3,
  Boxes,
  Building2,
  CheckCircle2,
  Clock,
  Cpu,
  Flame,
  Gauge,
  IndianRupee,
  Package,
  RefreshCw,
  Truck,
  Warehouse,
} from 'lucide-react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import PageHeader from '../components/common/PageHeader';
import StatCard from '../components/common/StatCard';
import StatusBadge from '../components/common/StatusBadge';
import DataTable from '../components/tables/DataTable';
import SupplyDemandChart from '../components/charts/SupplyDemandChart';
import { fetchAnalyticsOverview } from '../services/api';
import {
  extractApiError,
  formatCurrencyINR,
  formatNumber,
  formatPercent,
} from '../utils/formatters';

const STATUS_PIE_COLORS = {
  planned: '#64748b',
  dispatched: '#0d9488',
  in_transit: '#0284c7',
  partially_delivered: '#f97316',
  delivered: '#059669',
  cancelled: '#dc2626',
};

const TABS = [
  { id: 'supply', label: 'Supply Chain (Live)', icon: Boxes },
  { id: 'optimization', label: 'Optimization (Snapshot)', icon: Cpu },
  { id: 'dispatch', label: 'Dispatch & Fleet', icon: Truck },
  { id: 'scenarios', label: 'Disaster Scenarios', icon: Flame },
];

function EmptyChartBox({ message }) {
  return (
    <div className="flex h-60 items-center justify-center rounded-lg border border-dashed border-slate-200 bg-slate-50/70 px-6 text-center text-xs text-slate-500">
      {message}
    </div>
  );
}

export default function Analytics() {
  const [overview, setOverview] = useState(null);
  const [activeTab, setActiveTab] = useState('supply');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadAnalytics = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchAnalyticsOverview();
      setOverview(data);
    } catch (err) {
      setError(extractApiError(err, 'Unable to load analytics from FastAPI backend.'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAnalytics();
  }, [loadAnalytics]);

  const sc = overview?.supply_chain;
  const opt = overview?.optimization;
  const latestRun = opt?.latest_run;
  const disp = overview?.dispatch;
  const scen = overview?.scenarios;
  const latestSim = scen?.latest_simulation;

  const gapColumns = [
    { key: 'product_code', header: 'Code', sortable: true },
    { key: 'product_name', header: 'Medical Product', sortable: true },
    {
      key: 'total_supply',
      header: 'Available Supply',
      sortable: true,
      render: (r) => `${formatNumber(r.total_supply)} ${r.unit}`,
    },
    {
      key: 'total_open_demand',
      header: 'Actionable Demand',
      sortable: true,
      render: (r) => `${formatNumber(r.total_open_demand)} ${r.unit}`,
    },
    {
      key: 'net_balance',
      header: 'Net Balance',
      sortable: true,
      render: (r) => `${r.net_balance >= 0 ? '+' : ''}${formatNumber(r.net_balance)}`,
    },
    {
      key: 'shortage_flag',
      header: 'Balance Status',
      sortable: true,
      render: (r) => (
        <StatusBadge
          status={r.shortage_flag ? 'shortage' : 'adequate'}
          label={r.shortage_flag ? 'Controlled Shortage' : 'Adequate'}
        />
      ),
    },
  ];

  const scenarioTypeColumns = [
    { key: 'label', header: 'Disruption Type', sortable: true },
    { key: 'simulations_count', header: 'Runs', sortable: true },
    {
      key: 'avg_cost_delta',
      header: 'Avg Cost Delta',
      sortable: true,
      render: (r) => `${r.avg_cost_delta >= 0 ? '+' : ''}${formatCurrencyINR(r.avg_cost_delta)}`,
    },
    {
      key: 'avg_fulfillment_delta',
      header: 'Avg Fulfillment Delta',
      sortable: true,
      render: (r) => `${r.avg_fulfillment_delta >= 0 ? '+' : ''}${r.avg_fulfillment_delta}%`,
    },
    {
      key: 'avg_distance_delta',
      header: 'Avg Route Distance Delta',
      sortable: true,
      render: (r) => `${r.avg_distance_delta >= 0 ? '+' : ''}${r.avg_distance_delta} km`,
    },
    {
      key: 'avg_unmet_delta',
      header: 'Avg Unmet Demand Delta',
      sortable: true,
      render: (r) => `${r.avg_unmet_delta >= 0 ? '+' : ''}${formatNumber(r.avg_unmet_delta)} units`,
    },
  ];

  const scenarioComparisonChart = latestSim
    ? [
        {
          metric: 'Demand',
          Baseline: latestSim.baseline_metrics?.total_demand || 0,
          Disrupted: latestSim.disrupted_metrics?.total_demand || 0,
        },
        {
          metric: 'Allocated',
          Baseline: latestSim.baseline_metrics?.total_allocated || 0,
          Disrupted: latestSim.disrupted_metrics?.total_allocated || 0,
        },
        {
          metric: 'Unmet',
          Baseline: latestSim.baseline_metrics?.total_unmet_demand || 0,
          Disrupted: latestSim.disrupted_metrics?.total_unmet_demand || 0,
        },
      ]
    : [];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Performance Analytics & Decision Support Reports"
        badge="Dynamic Live & Historical KPIs"
        description="Unified Supply Chain, Operations Research Optimization, Google OR-Tools Dispatch, and Disaster Simulation analytics computed dynamically from the database."
        actions={
          <button
            type="button"
            onClick={loadAnalytics}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh Analytics
          </button>
        }
      />

      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-xs text-red-800">
          <strong>Analytics Error:</strong> {error}
        </div>
      )}

      {/* Scope Transparency Banner */}
      <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-xs text-slate-600 shadow-sm">
        <strong className="text-slate-900">KPI Scope Separation:</strong>{' '}
        <em>Supply Chain KPIs</em> reflect current live operational tables;{' '}
        <em>Optimization KPIs</em> reflect immutable historical solver snapshots;{' '}
        <em>Dispatch KPIs</em> aggregate persisted OR-Tools tours and confirmed deliveries;{' '}
        <em>Scenario Analytics</em> summarize isolated stress tests with zero live database mutation.
      </div>

      {/* Section Tabs */}
      <div className="border-b border-slate-200">
        <nav className="-mb-px flex flex-wrap gap-1">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              type="button"
              onClick={() => setActiveTab(id)}
              className={`inline-flex items-center gap-1.5 border-b-2 px-4 py-2.5 text-xs font-semibold transition ${
                activeTab === id
                  ? 'border-teal-600 text-teal-700'
                  : 'border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-800'
              }`}
            >
              <Icon className="h-3.5 w-3.5" />
              <span>{label}</span>
            </button>
          ))}
        </nav>
      </div>

      {/* TAB 1: SUPPLY CHAIN LIVE KPIs */}
      {activeTab === 'supply' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard
              title="Network Facilities"
              value={sc ? `${sc.total_warehouses} WH / ${sc.total_hospitals} Hosp` : '—'}
              subtitle={sc ? `${sc.total_products} essential medical products` : ''}
              icon={Warehouse}
              accent="teal"
              sourceTag="Live DB"
            />
            <StatCard
              title="Available Inventory"
              value={sc ? `${formatNumber(sc.available_inventory_units)} units` : '—'}
              subtitle={
                sc
                  ? `Utilization: ${formatPercent(sc.inventory_utilization_pct)} of ${formatNumber(
                      sc.total_storage_capacity_units
                    )} cap`
                  : ''
              }
              icon={Boxes}
              accent="emerald"
              sourceTag="Live DB"
            />
            <StatCard
              title="Actionable Demand"
              value={sc ? `${formatNumber(sc.total_actionable_demand_units)} units` : '—'}
              subtitle={
                sc
                  ? `Open: ${formatNumber(sc.open_demand_units)} · Partial: ${formatNumber(
                      sc.partially_fulfilled_demand_units
                    )} · Fulfilled: ${formatNumber(sc.fulfilled_demand_units)}`
                  : ''
              }
              icon={Building2}
              accent="orange"
              sourceTag="Live DB"
            />
            <StatCard
              title="Critical-Priority Demand"
              value={sc ? `${formatNumber(sc.critical_priority_demand_units)} units` : '—'}
              subtitle="Tier-1 actionable hospital demand"
              icon={AlertTriangle}
              accent="red"
              sourceTag="Live DB"
            />
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <SupplyDemandChart data={sc?.supply_demand_gap || []} />

            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <h3 className="text-sm font-semibold text-slate-900">
                Warehouse Inventory Utilization (%)
              </h3>
              <p className="mb-4 text-xs text-slate-500">
                Current stock vs. warehouse storage capacity (Live operational DB)
              </p>
              {sc?.warehouse_inventory_utilization?.length > 0 ? (
                <div className="h-64 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={sc.warehouse_inventory_utilization}
                      margin={{ top: 8, right: 16, left: 0, bottom: 8 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                      <XAxis dataKey="warehouse_code" tick={{ fontSize: 11 }} />
                      <YAxis domain={[0, 100]} unit="%" tick={{ fontSize: 11 }} />
                      <Tooltip formatter={(val) => `${Number(val).toFixed(2)}%`} />
                      <Bar dataKey="utilization_pct" name="Utilization %" fill="#0d9488" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <EmptyChartBox message="No warehouse inventory data available." />
              )}
            </div>
          </div>

          <DataTable
            columns={gapColumns}
            rows={sc?.supply_demand_gap || []}
            loading={loading}
            defaultSortKey="product_code"
            emptyMessage="No supply-demand gap records available."
          />
        </div>
      )}

      {/* TAB 2: OPTIMIZATION HISTORICAL SNAPSHOT KPIs */}
      {activeTab === 'optimization' && (
        <div className="space-y-6">
          {!latestRun ? (
            <EmptyChartBox message="No optimization runs found yet. Execute Transportation LP or Lexicographic Priority LP on the Optimization page." />
          ) : (
            <>
              <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-teal-200 bg-teal-50/70 px-4 py-3 text-xs">
                <div>
                  <strong className="text-slate-900">Historical Snapshot:</strong>{' '}
                  <span className="font-bold text-teal-800">{latestRun.run_code}</span> &bull;{' '}
                  {latestRun.model_type === 'lexicographic_priority'
                    ? '4-Stage Lexicographic Priority LP'
                    : 'Multi-Commodity Transportation LP'}{' '}
                  &bull; Executed in <strong>{latestRun.execution_time_ms} ms</strong>
                </div>
                <div className="flex items-center gap-2">
                  <StatusBadge status={latestRun.solver_status} />
                  <span className="text-slate-500">Total Runs Stored: {opt.total_runs}</span>
                </div>
              </div>

              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <StatCard
                  title="Run Demand Included"
                  value={`${formatNumber(latestRun.total_demand)} units`}
                  subtitle="Snapshot demand inside selected scope"
                  icon={BarChart3}
                  accent="slate"
                  sourceTag="Run Snapshot"
                />
                <StatCard
                  title="Allocated Quantity"
                  value={`${formatNumber(latestRun.total_allocated)} units`}
                  subtitle={`Unmet: ${formatNumber(latestRun.total_unmet_demand)} units`}
                  icon={CheckCircle2}
                  accent="emerald"
                  sourceTag="Run Snapshot"
                />
                <StatCard
                  title="Fulfillment Rate"
                  value={formatPercent(latestRun.fulfillment_percentage)}
                  subtitle="Allocated / Run Demand"
                  icon={Gauge}
                  accent="teal"
                  sourceTag="Run Snapshot"
                />
                <StatCard
                  title="Transportation Cost"
                  value={formatCurrencyINR(latestRun.total_cost)}
                  subtitle="Optimal PuLP CBC objective"
                  icon={IndianRupee}
                  accent="teal"
                  sourceTag="Run Snapshot"
                />
              </div>

              <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                {/* Fulfillment by Priority Tier */}
                <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
                  <h3 className="text-sm font-semibold text-slate-900">
                    Fulfillment by Hospital Priority Tier (%)
                  </h3>
                  <p className="mb-4 text-xs text-slate-500">
                    Snapshot from {latestRun.run_code}
                  </p>
                  {latestRun.priority_summary?.length > 0 ? (
                    <div className="h-64 w-full">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={latestRun.priority_summary}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                          <XAxis dataKey="priority_level" tick={{ fontSize: 11 }} />
                          <YAxis domain={[0, 100]} unit="%" tick={{ fontSize: 11 }} />
                          <Tooltip formatter={(val) => `${Number(val).toFixed(2)}%`} />
                          <Bar dataKey="fulfillment_pct" name="Fulfillment %" radius={[4, 4, 0, 0]}>
                            {latestRun.priority_summary.map((entry) => (
                              <Cell
                                key={entry.priority_level}
                                fill={
                                  entry.priority_level === 'critical'
                                    ? '#dc2626'
                                    : entry.priority_level === 'high'
                                    ? '#f97316'
                                    : '#059669'
                                }
                              />
                            ))}
                          </Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  ) : (
                    <EmptyChartBox message="Priority summary not recorded on this run." />
                  )}
                </div>

                {/* Transportation Cost Comparison across Recent Runs */}
                <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
                  <h3 className="text-sm font-semibold text-slate-900">
                    Transportation Cost Comparison Across Optimization Runs
                  </h3>
                  <p className="mb-4 text-xs text-slate-500">
                    Comparing persisted Transportation LP vs. Lexicographic Priority LP runs (INR)
                  </p>
                  {opt.cost_comparison_history?.length > 0 ? (
                    <div className="h-64 w-full">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={opt.cost_comparison_history}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                          <XAxis dataKey="short_label" tick={{ fontSize: 10 }} />
                          <YAxis tick={{ fontSize: 11 }} />
                          <Tooltip formatter={(val) => formatCurrencyINR(val)} />
                          <Bar
                            dataKey="total_cost"
                            name="Transport Cost (INR)"
                            fill="#132240"
                            radius={[4, 4, 0, 0]}
                          />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  ) : (
                    <EmptyChartBox message="Run multiple models to compare transportation cost." />
                  )}
                </div>

                {/* Hospital-wise Demand Fulfillment */}
                <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm lg:col-span-2">
                  <h3 className="text-sm font-semibold text-slate-900">
                    Hospital-Wise Demand Allocation vs. Unmet Shortage ({latestRun.run_code})
                  </h3>
                  <p className="mb-4 text-xs text-slate-500">
                    Allocated units vs. unmet units per hospital in latest historical run
                  </p>
                  {latestRun.hospital_summary?.length > 0 ? (
                    <div className="h-64 w-full">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={latestRun.hospital_summary}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                          <XAxis dataKey="hospital_code" tick={{ fontSize: 11 }} />
                          <YAxis tick={{ fontSize: 11 }} />
                          <Tooltip />
                          <Legend wrapperStyle={{ fontSize: 11 }} />
                          <Bar dataKey="total_allocated" name="Allocated Units" stackId="a" fill="#0d9488" />
                          <Bar dataKey="total_unmet" name="Unmet Units" stackId="a" fill="#ef4444" />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  ) : (
                    <EmptyChartBox message="No hospital-level summary recorded on this run." />
                  )}
                </div>
              </div>
            </>
          )}
        </div>
      )}

      {/* TAB 3: DISPATCH & FLEET KPIs */}
      {activeTab === 'dispatch' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard
              title="Dispatch Plans & Tours"
              value={disp ? `${disp.total_dispatch_plans} plan(s)` : '—'}
              subtitle={
                disp
                  ? `${disp.total_planned_routes} route(s) · ${disp.total_delivery_stops} hospital stop(s)`
                  : ''
              }
              icon={Truck}
              accent="teal"
              sourceTag="OR-Tools CVRP"
            />
            <StatCard
              title="Total Dispatched Payload"
              value={disp ? `${formatNumber(disp.total_dispatched_payload_kg)} kg` : '—'}
              subtitle={
                disp ? `Avg vehicle utilization: ${formatPercent(disp.average_vehicle_utilization_pct)}` : ''
              }
              icon={Package}
              accent="emerald"
              sourceTag="1D Weight Cap"
            />
            <StatCard
              title="Estimated Distance & Time"
              value={disp ? `${formatNumber(disp.total_estimated_distance_km)} km` : '—'}
              subtitle={
                disp ? `${formatNumber(disp.total_estimated_duration_min)} min (speed-profile est.)` : ''
              }
              icon={Clock}
              accent="slate"
              sourceTag={disp?.latest_plan_routing_source === 'osm' ? 'OSM Road Graph' : 'Dispatch History'}
            />
            <StatCard
              title="Dispatch Completion"
              value={disp ? formatPercent(disp.dispatch_completion_pct) : '—'}
              subtitle={
                disp
                  ? `Delivered: ${formatNumber(disp.total_delivered_quantity)} · Pending: ${formatNumber(
                      disp.total_pending_quantity
                    )} units`
                  : ''
              }
              icon={CheckCircle2}
              accent="teal"
              sourceTag="Shipment Lines"
            />
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            {/* Vehicle Payload Utilization */}
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <h3 className="text-sm font-semibold text-slate-900">
                Vehicle Payload Utilization (%) — {disp?.latest_plan_code || 'Latest Dispatch Plan'}
              </h3>
              <p className="mb-4 text-xs text-slate-500">
                Assigned weight load vs. rated payload capacity (kg) per vehicle wave
              </p>
              {disp?.vehicle_utilization_chart?.length > 0 ? (
                <div className="h-64 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={disp.vehicle_utilization_chart}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                      <XAxis dataKey="label" tick={{ fontSize: 10 }} />
                      <YAxis domain={[0, 100]} unit="%" tick={{ fontSize: 11 }} />
                      <Tooltip formatter={(val) => `${Number(val).toFixed(1)}%`} />
                      <Bar dataKey="utilization_pct" name="Payload Utilization %" fill="#0d9488" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <EmptyChartBox message="Generate a dispatch plan on the Delivery Routes page to inspect vehicle utilization." />
              )}
            </div>

            {/* Dispatch Stop Status Breakdown */}
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <h3 className="text-sm font-semibold text-slate-900">
                Delivery Stop Lifecycle Breakdown
              </h3>
              <p className="mb-4 text-xs text-slate-500">
                Distribution of persisted hospital delivery stops across lifecycle states
              </p>
              {disp?.status_breakdown?.length > 0 ? (
                <div className="h-64 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={disp.status_breakdown}
                        dataKey="count"
                        nameKey="label"
                        cx="50%"
                        cy="50%"
                        outerRadius={85}
                        label={({ label, count }) => `${label}: ${count}`}
                      >
                        {disp.status_breakdown.map((entry) => (
                          <Cell
                            key={entry.status}
                            fill={STATUS_PIE_COLORS[entry.status] || '#0d9488'}
                          />
                        ))}
                      </Pie>
                      <Tooltip />
                      <Legend wrapperStyle={{ fontSize: 11 }} />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <EmptyChartBox message="No persisted delivery stops yet." />
              )}
            </div>
          </div>
        </div>
      )}

      {/* TAB 4: DISASTER SCENARIO ANALYTICS */}
      {activeTab === 'scenarios' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard
              title="Total Simulations"
              value={scen ? formatNumber(scen.total_simulations) : '—'}
              subtitle="Persisted immutable stress tests"
              icon={Flame}
              accent="orange"
              sourceTag="Isolated"
            />
            <StatCard
              title="Latest Cost Impact"
              value={
                latestSim
                  ? `${(latestSim.comparison?.transport_cost_delta || 0) >= 0 ? '+' : ''}${formatCurrencyINR(
                      latestSim.comparison?.transport_cost_delta || 0
                    )}`
                  : '—'
              }
              subtitle={latestSim ? latestSim.simulation_code : 'No simulations yet'}
              icon={IndianRupee}
              accent="slate"
              sourceTag="Delta"
            />
            <StatCard
              title="Latest Fulfillment Shift"
              value={
                latestSim
                  ? `${(latestSim.comparison?.fulfillment_pct_delta || 0) >= 0 ? '+' : ''}${
                      latestSim.comparison?.fulfillment_pct_delta || 0
                    }%`
                  : '—'
              }
              subtitle={
                latestSim
                  ? `Unmet delta: ${(latestSim.comparison?.unmet_demand_delta || 0) >= 0 ? '+' : ''}${formatNumber(
                      latestSim.comparison?.unmet_demand_delta || 0
                    )} units`
                  : ''
              }
              icon={Activity}
              accent="red"
              sourceTag="Delta"
            />
            <StatCard
              title="Latest Route Distance Shift"
              value={
                latestSim
                  ? `${(latestSim.comparison?.route_distance_km_delta || 0) >= 0 ? '+' : ''}${
                      latestSim.comparison?.route_distance_km_delta || 0
                    } km`
                  : '—'
              }
              subtitle={latestSim ? `Routing: ${latestSim.routing_source}` : ''}
              icon={Truck}
              accent="teal"
              sourceTag="OR-Tools"
            />
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <h3 className="text-sm font-semibold text-slate-900">
                Baseline vs. Disrupted Volume — {latestSim?.scenario_name || 'Latest Simulation'}
              </h3>
              <p className="mb-4 text-xs text-slate-500">
                Side-by-side comparison of demand, allocation, and unmet shortage
              </p>
              {scenarioComparisonChart.length > 0 ? (
                <div className="h-64 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={scenarioComparisonChart}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                      <XAxis dataKey="metric" tick={{ fontSize: 11 }} />
                      <YAxis tick={{ fontSize: 11 }} />
                      <Tooltip />
                      <Legend wrapperStyle={{ fontSize: 11 }} />
                      <Bar dataKey="Baseline" fill="#0d9488" radius={[4, 4, 0, 0]} />
                      <Bar dataKey="Disrupted" fill="#dc2626" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <EmptyChartBox message="Run a disruption scenario on the Scenario Simulator page to view impact charts." />
              )}
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <h3 className="text-sm font-semibold text-slate-900">
                Average Impact by Disruption Category
              </h3>
              <p className="mb-4 text-xs text-slate-500">
                Aggregated fulfillment (%) and unmet demand changes across simulation types
              </p>
              {scen?.impact_by_type?.length > 0 ? (
                <div className="h-64 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={scen.impact_by_type}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                      <XAxis dataKey="label" tick={{ fontSize: 10 }} />
                      <YAxis tick={{ fontSize: 11 }} />
                      <Tooltip />
                      <Legend wrapperStyle={{ fontSize: 11 }} />
                      <Bar
                        dataKey="avg_unmet_delta"
                        name="Avg Unmet Demand Delta (units)"
                        fill="#f97316"
                        radius={[4, 4, 0, 0]}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <EmptyChartBox message="No scenario impact statistics available yet." />
              )}
            </div>
          </div>

          <DataTable
            columns={scenarioTypeColumns}
            rows={scen?.impact_by_type || []}
            loading={loading}
            defaultSortKey="label"
            emptyMessage="No disaster scenario simulations recorded yet."
          />
        </div>
      )}
    </div>
  );
}
