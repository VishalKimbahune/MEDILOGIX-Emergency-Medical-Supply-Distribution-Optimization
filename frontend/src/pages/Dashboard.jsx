import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  AlertTriangle,
  Boxes,
  Building2,
  ClipboardList,
  Gauge,
  IndianRupee,
  TrendingUp,
  Warehouse,
} from 'lucide-react';
import PageHeader from '../components/common/PageHeader';
import StatCard from '../components/common/StatCard';
import PuneNetworkMap from '../components/maps/PuneNetworkMap';
import RecentRunsCard from '../components/dashboard/RecentRunsCard';
import { fetchAnalyticsSummary } from '../services/api';
import { warehouseService } from '../services/warehouseService';
import { hospitalService } from '../services/hospitalService';
import { optimizationService } from '../services/optimizationService';
import {
  formatCurrencyINR,
  formatNumber,
  formatPercent,
} from '../utils/formatters';

export default function Dashboard() {
  const [summary, setSummary] = useState(null);
  const [warehouses, setWarehouses] = useState([]);
  const [hospitals, setHospitals] = useState([]);
  const [runs, setRuns] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    let mounted = true;
    async function loadDashboard() {
      try {
        const [sumData, whData, hospData, runData] = await Promise.all([
          fetchAnalyticsSummary(),
          warehouseService.list(),
          hospitalService.list(),
          optimizationService.listRuns(),
        ]);
        if (mounted) {
          setSummary(sumData);
          setWarehouses(whData);
          setHospitals(hospData);
          setRuns(runData);
          setError(null);
        }
      } catch {
        if (mounted) {
          setError(
            'Unable to load live metrics from FastAPI backend. Start uvicorn on port 8000 and initialize the database.'
          );
        }
      }
    }
    loadDashboard();
    return () => {
      mounted = false;
    };
  }, []);

  const tag = summary ? 'Live API' : 'Awaiting API';

  return (
    <div>
      <PageHeader
        title="Emergency Command Dashboard"
        badge="Pune & PCMC"
        description="Operational overview of medical warehouses, hospital priorities, open supply demand, and Operations Research runs."
      />

      {error && (
        <div className="mb-6 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs text-amber-900">
          <strong>Backend Not Connected:</strong> {error} (No fake fallback metrics are displayed.)
        </div>
      )}

      {(summary?.pending_user_approvals_count > 0 || summary?.pending_order_approvals_count > 0) && (
        <div className="mb-6 grid grid-cols-1 gap-3 sm:grid-cols-2">
          {summary?.pending_user_approvals_count > 0 && (
            <div className="flex items-center justify-between rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs text-amber-900">
              <span>
                <strong>{summary.pending_user_approvals_count}</strong> account registration(s)
                pending admin approval.
              </span>
              <Link
                to="/admin/users"
                className="font-bold text-amber-900 underline hover:text-amber-700"
              >
                Review Users
              </Link>
            </div>
          )}
          {summary?.pending_order_approvals_count > 0 && (
            <div className="flex items-center justify-between rounded-xl border border-sky-200 bg-sky-50 px-4 py-3 text-xs text-sky-900">
              <span>
                <strong>{summary.pending_order_approvals_count}</strong> hospital order(s) (
                {formatNumber(summary.pending_approval_demand_units)} units) awaiting approval.
              </span>
              <Link
                to="/admin/demands"
                className="font-bold text-sky-900 underline hover:text-sky-700"
              >
                Review Orders
              </Link>
            </div>
          )}
        </div>
      )}

      {/* Primary KPI Grid */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          title="Total Warehouses"
          value={summary ? formatNumber(summary.total_warehouses) : '—'}
          subtitle="Fictional simulation hubs"
          icon={Warehouse}
          accent="teal"
          sourceTag={tag}
        />
        <StatCard
          title="Total Hospitals"
          value={summary ? formatNumber(summary.total_hospitals) : '—'}
          subtitle="Synthetic hospital profiles"
          icon={Building2}
          accent="slate"
          sourceTag={tag}
        />
        <StatCard
          title="Available Inventory"
          value={summary ? `${formatNumber(summary.available_inventory_units)} units` : '—'}
          subtitle="Across all 4 medical products"
          icon={Boxes}
          accent="emerald"
          sourceTag={tag}
        />
        <StatCard
          title="Current Open Demand"
          value={summary ? `${formatNumber(summary.total_open_demand_units)} units` : '—'}
          subtitle={
            summary?.total_partially_fulfilled_demand_units > 0
              ? `+ ${formatNumber(summary.total_partially_fulfilled_demand_units)} partially fulfilled (${formatNumber(
                  summary.total_actionable_demand_units
                )} actionable)`
              : 'Live open hospital requests'
          }
          icon={ClipboardList}
          accent="orange"
          sourceTag={tag}
        />
        <StatCard
          title="Critical Hospital Alerts"
          value={summary ? formatNumber(summary.critical_hospital_alerts) : '—'}
          subtitle="Tier-1 lexicographic priority"
          icon={AlertTriangle}
          accent="red"
          sourceTag={tag}
        />
        <StatCard
          title="Inventory Utilization"
          value={summary ? formatPercent(summary.inventory_utilization_pct) : '—'}
          subtitle="Stock vs. warehouse capacity"
          icon={Gauge}
          accent="teal"
          sourceTag={tag}
        />
        <StatCard
          title="Fulfillment (Latest Run)"
          value={
            summary?.latest_demand_fulfillment_pct !== null &&
            summary?.latest_demand_fulfillment_pct !== undefined
              ? formatPercent(summary.latest_demand_fulfillment_pct)
              : 'Not solved yet'
          }
          subtitle={
            summary?.latest_run_code
              ? `${summary.latest_run_code} · ${formatNumber(
                  summary.latest_run_total_allocated
                )} / ${formatNumber(summary.latest_run_total_demand)} units`
              : 'Run OR optimizer to compute'
          }
          icon={TrendingUp}
          accent="emerald"
          sourceTag={summary?.latest_run_code ? 'Run Snapshot' : 'Pending Run'}
        />
        <StatCard
          title="Distribution Cost"
          value={
            summary?.latest_distribution_cost !== null &&
            summary?.latest_distribution_cost !== undefined
              ? formatCurrencyINR(summary.latest_distribution_cost)
              : 'Not solved yet'
          }
          subtitle="Optimal LP transport cost"
          icon={IndianRupee}
          accent="teal"
          sourceTag={summary?.latest_run_code ? 'Latest Solver Run' : 'Pending Run'}
        />
      </div>

      {/* Interactive Geographical Map + Recent Runs */}
      <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-3">
        <div className="xl:col-span-2">
          <PuneNetworkMap warehouses={warehouses} hospitals={hospitals} />
        </div>
        <div>
          <RecentRunsCard runs={runs} />
        </div>
      </div>
    </div>
  );
}
