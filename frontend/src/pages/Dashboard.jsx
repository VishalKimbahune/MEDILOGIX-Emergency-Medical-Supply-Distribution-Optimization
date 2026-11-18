import React, { useEffect, useState } from 'react';
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
          title="Total Open Demand"
          value={summary ? `${formatNumber(summary.total_open_demand_units)} units` : '—'}
          subtitle="Unfulfilled & open requests"
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
          title="Demand Fulfillment"
          value={
            summary?.latest_demand_fulfillment_pct !== null &&
            summary?.latest_demand_fulfillment_pct !== undefined
              ? formatPercent(summary.latest_demand_fulfillment_pct)
              : 'Not solved yet'
          }
          subtitle={summary?.latest_run_code || 'Run OR optimizer to compute'}
          icon={TrendingUp}
          accent="emerald"
          sourceTag={summary?.latest_run_code ? 'Latest Solver Run' : 'Pending Run'}
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
