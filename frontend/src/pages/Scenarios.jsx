import React, { useCallback, useEffect, useState } from 'react';
import {
  AlertTriangle,
  BarChart3,
  Eye,
  Flame,
  History,
  Map as MapIcon,
  Play,
  RefreshCw,
  ShieldCheck,
  Truck,
} from 'lucide-react';
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
import PageHeader from '../components/common/PageHeader';
import StatusBadge from '../components/common/StatusBadge';
import DataTable from '../components/tables/DataTable';
import PuneNetworkMap from '../components/maps/PuneNetworkMap';
import { useToast } from '../components/common/ToastContext';
import { scenarioService } from '../services/scenarioService';
import { optimizationService } from '../services/optimizationService';
import { warehouseService } from '../services/warehouseService';
import { hospitalService } from '../services/hospitalService';
import { routeService } from '../services/routeService';
import {
  extractApiError,
  formatCurrencyINR,
  formatNumber,
  formatPercent,
} from '../utils/formatters';

const SCENARIO_TYPES = [
  { value: 'warehouse_outage', label: 'Warehouse Outage' },
  { value: 'road_closure', label: 'Road Corridor Closure' },
  { value: 'demand_spike', label: 'Hospital Demand Spike' },
  { value: 'vehicle_unavailability', label: 'Vehicle Unavailability' },
  { value: 'combined', label: 'Combined Multi-Factor Disruption' },
];

function ComparisonMetricCard({ label, baseline, disrupted, deltaText, negativeIsGood = false, isWorse = false }) {
  const badgeClass =
    deltaText === '0' || deltaText === '0.0%' || deltaText === '+0'
      ? 'bg-slate-100 text-slate-600'
      : isWorse
      ? 'bg-red-50 text-red-700'
      : negativeIsGood
      ? 'bg-emerald-50 text-emerald-700'
      : 'bg-teal-50 text-teal-800';

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between gap-2">
        <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
          {label}
        </p>
        <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${badgeClass}`}>
          {deltaText}
        </span>
      </div>
      <div className="mt-2.5 flex items-baseline justify-between gap-2">
        <div>
          <p className="text-[10px] text-slate-400">Baseline</p>
          <p className="text-sm font-semibold text-slate-600">{baseline}</p>
        </div>
        <div className="text-right">
          <p className="text-[10px] text-slate-400">Disrupted</p>
          <p className="text-lg font-bold text-slate-900">{disrupted}</p>
        </div>
      </div>
    </div>
  );
}

export default function Scenarios() {
  const toast = useToast();

  // Reference network data
  const [warehouses, setWarehouses] = useState([]);
  const [hospitals, setHospitals] = useState([]);
  const [corridors, setCorridors] = useState([]);
  const [vehicles, setVehicles] = useState([]);
  const [optRuns, setOptRuns] = useState([]);
  const [simHistory, setSimHistory] = useState([]);
  const [activeSim, setActiveSim] = useState(null);

  // Configuration state
  const [baselineRunId, setBaselineRunId] = useState('');
  const [scenarioName, setScenarioName] = useState('');
  const [scenarioType, setScenarioType] = useState('combined');
  const [disabledWarehouses, setDisabledWarehouses] = useState([]);
  const [closedRoutes, setClosedRoutes] = useState([]);
  const [closedWayIdsInput, setClosedWayIdsInput] = useState('');
  const [spikeHospitals, setSpikeHospitals] = useState([]);
  const [demandSpikePct, setDemandSpikePct] = useState(0);
  const [disabledVehicles, setDisabledVehicles] = useState([]);

  // UI state
  const [loading, setLoading] = useState(true);
  const [simulating, setSimulating] = useState(false);
  const [activeTab, setActiveTab] = useState('impact'); // impact | map | history
  const [error, setError] = useState(null);

  const loadContext = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [whRows, hospRows, corRows, vehRows, runRows, simRows] = await Promise.all([
        warehouseService.list(),
        hospitalService.list(),
        routeService.listCorridors(),
        routeService.listVehicles(),
        optimizationService.listRuns(),
        scenarioService.listSimulationRuns(),
      ]);
      setWarehouses(whRows);
      setHospitals(hospRows);
      setCorridors(corRows);
      setVehicles(vehRows);
      const optimalRuns = runRows.filter((r) => r.solver_status === 'Optimal');
      setOptRuns(optimalRuns);
      setSimHistory(simRows);

      if (optimalRuns.length > 0) {
        setBaselineRunId((prev) => prev || String(optimalRuns[0].id));
      }
      if (simRows.length > 0) {
        setActiveSim((prev) => {
          if (prev) return prev;
          scenarioService
            .getSimulationRun(simRows[0].id)
            .then(setActiveSim)
            .catch(() => {});
          return prev;
        });
      }
    } catch (err) {
      setError(extractApiError(err, 'Unable to load scenario simulator data from backend API.'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadContext();
  }, [loadContext]);

  function toggleItem(code, list, setter) {
    if (list.includes(code)) {
      setter(list.filter((c) => c !== code));
    } else {
      setter([...list, code]);
    }
  }

  async function handleRunSimulation() {
    if (!baselineRunId) {
      toast.warning('Select baseline run', 'Run an optimization on the Optimization page first.');
      return;
    }

    const useWh =
      scenarioType === 'warehouse_outage' || scenarioType === 'combined'
        ? disabledWarehouses
        : [];
    const useRoutes =
      scenarioType === 'road_closure' || scenarioType === 'combined' ? closedRoutes : [];
    const parsedClosedWays =
      scenarioType === 'road_closure' || scenarioType === 'combined'
        ? closedWayIdsInput
            .split(/[,\s]+/)
            .map((t) => t.trim())
            .filter(Boolean)
            .map((t) => Number(t))
            .filter((n) => Number.isInteger(n) && n > 0)
        : [];
    const useSpikeHosp =
      scenarioType === 'demand_spike' || scenarioType === 'combined' ? spikeHospitals : [];
    const useSpikePct =
      scenarioType === 'demand_spike' || scenarioType === 'combined' ? Number(demandSpikePct) : 0;
    const useVeh =
      scenarioType === 'vehicle_unavailability' || scenarioType === 'combined'
        ? disabledVehicles
        : [];

    if (
      useWh.length === 0 &&
      useRoutes.length === 0 &&
      parsedClosedWays.length === 0 &&
      useSpikePct <= 0 &&
      useVeh.length === 0
    ) {
      toast.warning(
        'Select at least one disruption',
        'Configure a warehouse outage, road closure, OSM way closure, demand spike %, or unavailable vehicle.'
      );
      return;
    }

    setSimulating(true);
    setError(null);
    try {
      const result = await scenarioService.runSimulation({
        baseline_run_id: Number(baselineRunId),
        name: scenarioName.trim() || undefined,
        scenario_type: scenarioType,
        disabled_warehouse_codes: useWh,
        closed_route_codes: useRoutes,
        closed_way_ids: parsedClosedWays,
        demand_spike_hospital_codes: useSpikeHosp,
        demand_spike_pct: useSpikePct,
        disabled_vehicle_codes: useVeh,
      });
      setActiveSim(result);
      const updatedHist = await scenarioService.listSimulationRuns();
      setSimHistory(updatedHist);
      setActiveTab('impact');
      toast.success(
        'Disaster simulation completed',
        `${result.simulation_code}: Baseline preserved; live data untouched.`
      );
    } catch (err) {
      const msg = extractApiError(err, 'Failed to run disaster scenario simulation.');
      setError(msg);
      toast.error('Simulation failed', msg);
    } finally {
      setSimulating(false);
    }
  }

  async function handleInspectSimulation(simId) {
    try {
      const detail = await scenarioService.getSimulationRun(simId);
      setActiveSim(detail);
      setActiveTab('impact');
      toast.info('Simulation loaded', `Inspecting ${detail.simulation_code}.`);
    } catch (err) {
      toast.error('Load failed', extractApiError(err, 'Could not load simulation details.'));
    }
  }

  const baseM = activeSim?.baseline_metrics;
  const disM = activeSim?.disrupted_metrics;
  const comp = activeSim?.comparison || {};

  const tierChartData = activeSim
    ? [
        {
          tier: 'Critical',
          Baseline: baseM.critical_fulfillment_pct,
          Disrupted: disM.critical_fulfillment_pct,
        },
        {
          tier: 'High',
          Baseline: baseM.high_fulfillment_pct,
          Disrupted: disM.high_fulfillment_pct,
        },
        {
          tier: 'Normal',
          Baseline: baseM.normal_fulfillment_pct,
          Disrupted: disM.normal_fulfillment_pct,
        },
      ]
    : [];

  const volumeChartData = activeSim
    ? [
        { metric: 'Total Demand', Baseline: baseM.total_demand, Disrupted: disM.total_demand },
        { metric: 'Allocated', Baseline: baseM.total_allocated, Disrupted: disM.total_allocated },
        { metric: 'Unmet Demand', Baseline: baseM.total_unmet_demand, Disrupted: disM.total_unmet_demand },
      ]
    : [];

  const historyColumns = [
    {
      key: 'simulation_code',
      header: 'Simulation ID',
      sortable: true,
      render: (r) => (
        <div>
          <span className="font-semibold text-slate-900">{r.simulation_code}</span>
          {activeSim?.id === r.id && (
            <span className="ml-2 rounded bg-teal-50 px-1.5 py-0.5 text-[10px] font-bold text-teal-700">
              Viewing
            </span>
          )}
        </div>
      ),
    },
    { key: 'scenario_name', header: 'Scenario Name', sortable: true },
    {
      key: 'scenario_type',
      header: 'Type',
      sortable: true,
      render: (r) => <span className="capitalize">{r.scenario_type.replace(/_/g, ' ')}</span>,
    },
    { key: 'baseline_run_code', header: 'Baseline Run', sortable: true },
    {
      key: 'status',
      header: 'Outcome',
      sortable: true,
      render: (r) => <StatusBadge status={r.status} />,
    },
    {
      key: 'crit_shift',
      header: 'Critical Fulfillment',
      render: (r) =>
        `${formatPercent(r.baseline_metrics.critical_fulfillment_pct)} → ${formatPercent(
          r.disrupted_metrics.critical_fulfillment_pct
        )}`,
    },
    {
      key: 'actions',
      header: 'Inspect',
      render: (r) => (
        <button
          type="button"
          onClick={() => handleInspectSimulation(r.id)}
          className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-xs font-semibold text-slate-700 hover:border-teal-300 hover:bg-teal-50 hover:text-teal-700"
        >
          <Eye className="h-3.5 w-3.5" />
          Inspect
        </button>
      ),
    },
  ];

  const showWh = scenarioType === 'warehouse_outage' || scenarioType === 'combined';
  const showRoutes = scenarioType === 'road_closure' || scenarioType === 'combined';
  const showSpike = scenarioType === 'demand_spike' || scenarioType === 'combined';
  const showVeh = scenarioType === 'vehicle_unavailability' || scenarioType === 'combined';

  return (
    <div className="space-y-6">
      <PageHeader
        title="Disaster & Disruption Scenario Simulator"
        badge="Isolated Stress Testing"
        description="Simulate warehouse outages, road closures, hospital demand spikes, and vehicle fleet losses against a baseline run without mutating live operational data."
        actions={
          <button
            type="button"
            onClick={loadContext}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        }
      />

      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-xs text-red-800">
          <strong>Simulation Error:</strong> {error}
        </div>
      )}

      {/* Scenario Builder Card */}
      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-3">
          <div className="flex items-center gap-2">
            <Flame className="h-4 w-4 text-orange-500" />
            <h2 className="text-sm font-bold text-slate-900">Configure Disruption Scenario</h2>
          </div>
          <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-800">
            <ShieldCheck className="h-3.5 w-3.5" />
            Zero Live DB Mutation
          </span>
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <div>
            <label className="block text-xs font-semibold text-slate-700">
              Baseline Optimization Run
            </label>
            <select
              value={baselineRunId}
              onChange={(e) => setBaselineRunId(e.target.value)}
              className="mt-1 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs text-slate-900 focus:border-teal-600 focus:outline-none"
            >
              {optRuns.length === 0 ? (
                <option value="">No completed optimization runs available</option>
              ) : (
                optRuns.map((run) => (
                  <option key={run.id} value={String(run.id)}>
                    {run.run_code} ({run.model_type === 'lexicographic_priority' ? 'Priority' : 'Transport'}) — {formatCurrencyINR(run.total_cost)}
                  </option>
                ))
              )}
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700">
              Disruption Type
            </label>
            <select
              value={scenarioType}
              onChange={(e) => setScenarioType(e.target.value)}
              className="mt-1 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs text-slate-900 focus:border-teal-600 focus:outline-none"
            >
              {SCENARIO_TYPES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700">
              Scenario Name (Optional)
            </label>
            <input
              type="text"
              value={scenarioName}
              onChange={(e) => setScenarioName(e.target.value)}
              placeholder="e.g., Monsoon Flood + Swargate Outage"
              className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-xs text-slate-900 focus:border-teal-600 focus:outline-none"
            />
          </div>
        </div>

        {/* Disruption Selectors */}
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {showWh && (
            <div className="rounded-lg border border-slate-200 bg-slate-50/60 p-3.5">
              <p className="text-xs font-bold text-slate-800">
                A. Warehouse Outage ({disabledWarehouses.length} selected)
              </p>
              <p className="text-[11px] text-slate-500">
                Temporarily disables warehouse supply and its assigned fleet.
              </p>
              <div className="mt-2.5 flex flex-wrap gap-1.5">
                {warehouses.map((wh) => {
                  const selected = disabledWarehouses.includes(wh.code);
                  return (
                    <button
                      key={wh.code}
                      type="button"
                      onClick={() => toggleItem(wh.code, disabledWarehouses, setDisabledWarehouses)}
                      className={`rounded-md border px-2.5 py-1 text-xs font-semibold transition ${
                        selected
                          ? 'border-red-600 bg-red-600 text-white'
                          : 'border-slate-200 bg-white text-slate-700 hover:bg-slate-100'
                      }`}
                    >
                      {wh.code} ({wh.area})
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {showVeh && (
            <div className="rounded-lg border border-slate-200 bg-slate-50/60 p-3.5">
              <p className="text-xs font-bold text-slate-800">
                D. Vehicle Unavailability ({disabledVehicles.length} selected)
              </p>
              <p className="text-[11px] text-slate-500">
                Removes selected vehicles from OR-Tools CVRP routing capacity.
              </p>
              <div className="mt-2.5 flex flex-wrap gap-1.5">
                {vehicles.map((v) => {
                  const selected = disabledVehicles.includes(v.vehicle_code);
                  return (
                    <button
                      key={v.vehicle_code}
                      type="button"
                      onClick={() => toggleItem(v.vehicle_code, disabledVehicles, setDisabledVehicles)}
                      className={`rounded-md border px-2.5 py-1 text-xs font-medium transition ${
                        selected
                          ? 'border-orange-600 bg-orange-500 text-white'
                          : 'border-slate-200 bg-white text-slate-700 hover:bg-slate-100'
                      }`}
                    >
                      {v.vehicle_code} ({formatNumber(v.capacity_kg)} kg)
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {showSpike && (
            <div className="rounded-lg border border-slate-200 bg-slate-50/60 p-3.5">
              <div className="flex items-center justify-between gap-2">
                <div>
                  <p className="text-xs font-bold text-slate-800">
                    C. Hospital Demand Spike (+{demandSpikePct}%)
                  </p>
                  <p className="text-[11px] text-slate-500">
                    Leave hospitals unselected to apply across all active hospitals.
                  </p>
                </div>
                <input
                  type="number"
                  min="0"
                  max="300"
                  step="5"
                  value={demandSpikePct}
                  onChange={(e) => setDemandSpikePct(Math.max(0, Number(e.target.value)))}
                  className="w-20 rounded-lg border border-slate-300 bg-white px-2 py-1 text-xs font-bold text-slate-900"
                />
              </div>
              <input
                type="range"
                min="0"
                max="150"
                step="5"
                value={Math.min(150, demandSpikePct)}
                onChange={(e) => setDemandSpikePct(Number(e.target.value))}
                className="mt-2 w-full accent-teal-600"
              />
              <div className="mt-2 flex flex-wrap gap-1.5">
                {hospitals.map((h) => {
                  const selected = spikeHospitals.includes(h.code);
                  return (
                    <button
                      key={h.code}
                      type="button"
                      onClick={() => toggleItem(h.code, spikeHospitals, setSpikeHospitals)}
                      className={`rounded-md border px-2 py-1 text-xs font-medium transition ${
                        selected
                          ? 'border-red-600 bg-red-50 text-red-800'
                          : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-100'
                      }`}
                    >
                      {h.code} ({h.area})
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {showRoutes && (
            <div className="rounded-lg border border-slate-200 bg-slate-50/60 p-3.5">
              <p className="text-xs font-bold text-slate-800">
                B. Road Corridor Closures ({closedRoutes.length} closed)
              </p>
              <p className="text-[11px] text-slate-500">
                Blocks selected warehouse-hospital corridors in both Phase 3 LP and Phase 4A OR-Tools VRP.
              </p>
              <div className="mt-2.5 flex max-h-32 flex-wrap gap-1.5 overflow-y-auto pr-1">
                {corridors.map((c) => {
                  const selected = closedRoutes.includes(c.route_code);
                  return (
                    <button
                      key={c.route_code}
                      type="button"
                      onClick={() => toggleItem(c.route_code, closedRoutes, setClosedRoutes)}
                      className={`rounded-md border px-2 py-1 text-[11px] font-medium transition ${
                        selected
                          ? 'border-red-600 bg-red-600 text-white'
                          : 'border-slate-200 bg-white text-slate-700 hover:bg-slate-100'
                      }`}
                    >
                      {c.route_code}: {c.warehouse_code}&rarr;{c.hospital_code}
                    </button>
                  );
                })}
              </div>
              <div className="mt-2.5 border-t border-slate-200 pt-2">
                <label className="block text-[11px] font-semibold text-slate-700">
                  Optional OSM Way ID Closures (comma-separated)
                </label>
                <input
                  type="text"
                  value={closedWayIdsInput}
                  onChange={(e) => setClosedWayIdsInput(e.target.value)}
                  placeholder="e.g., 210788741 (excluded only in isolated simulation)"
                  className="mt-1 block w-full rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-xs text-slate-900 focus:border-teal-600 focus:outline-none"
                />
              </div>
            </div>
          )}
        </div>

        <div className="flex justify-end">
          <button
            type="button"
            disabled={simulating || !baselineRunId}
            onClick={handleRunSimulation}
            className="inline-flex items-center gap-2 rounded-lg bg-teal-600 px-5 py-2.5 text-xs font-semibold text-white shadow-sm hover:bg-teal-700 disabled:opacity-50"
          >
            <Play className="h-3.5 w-3.5" />
            {simulating ? 'Re-solving LP + OR-Tools VRP...' : 'Run Disaster Simulation'}
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-slate-200">
        <nav className="-mb-px flex flex-wrap gap-1">
          {[
            { id: 'impact', label: 'Baseline vs. Disrupted Impact', icon: BarChart3 },
            { id: 'map', label: 'Disruption & Route Map', icon: MapIcon },
            { id: 'history', label: 'Simulation History', icon: History },
          ].map(({ id, label, icon: Icon }) => (
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
              {id === 'history' && (
                <span className="rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-600">
                  {simHistory.length}
                </span>
              )}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab Content */}
      {activeTab === 'history' ? (
        <DataTable
          columns={historyColumns}
          rows={simHistory}
          loading={loading}
          emptyMessage="No disaster simulations executed yet."
        />
      ) : !activeSim ? (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white p-10 text-center">
          <Truck className="mx-auto h-8 w-8 text-teal-600" />
          <h3 className="mt-3 text-sm font-bold text-slate-900">
            Configure a Disruption &amp; Run Simulation
          </h3>
          <p className="mx-auto mt-1.5 max-w-xl text-xs text-slate-600">
            Compare your baseline optimization run against recalculated LP allocations and OR-Tools
            vehicle routes under emergency disruptions.
          </p>
        </div>
      ) : activeTab === 'map' ? (
        <PuneNetworkMap
          warehouses={warehouses}
          hospitals={hospitals}
          vehicleRoutes={activeSim.disrupted_routes || []}
          closedCorridors={activeSim.closed_corridors || []}
          closedOsmWays={activeSim.closed_osm_ways || []}
          disabledWarehouses={activeSim.disabled_warehouses || []}
          unreachableHospitals={activeSim.unreachable_hospitals || []}
          routingSource={activeSim.routing_source || null}
          routingObjective={activeSim.routing_objective || null}
          fallbackWarning={activeSim.fallback_warning || null}
          title={`Scenario ${activeSim.simulation_code} — ${activeSim.scenario_name}`}
          subtitle="Showing recalculated feasible OR-Tools routes on OSM street geometry (or fallback), disabled hubs, and closed roads (speed-profile estimates; not live traffic)"
          heightClass="h-[480px]"
        />
      ) : (
        <div className="space-y-6">
          {/* Summary Banner */}
          <div className="rounded-xl border border-teal-200 bg-teal-50/70 p-5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <span className="rounded bg-navy-900 px-2 py-0.5 text-xs font-bold text-white">
                  {activeSim.simulation_code}
                </span>
                <h3 className="text-sm font-bold text-slate-900">{activeSim.scenario_name}</h3>
                <StatusBadge status={activeSim.status} />
              </div>
              <span className="text-xs text-slate-600">
                Baseline: <strong>{activeSim.baseline_run_code}</strong> &bull; Solved in{' '}
                <strong>{activeSim.execution_time_ms} ms</strong>
              </span>
            </div>
            <p className="mt-2 text-xs leading-relaxed text-slate-700">{comp.summary_text}</p>
            {disM.infeasibility_reasons?.length > 0 && (
              <div className="mt-3 flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-800">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-red-600" />
                <div>
                  <strong>Routing Constraints Hit:</strong> {disM.infeasibility_reasons.join(' ')}
                </div>
              </div>
            )}
          </div>

          {/* All 11 Required Comparison KPIs */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <ComparisonMetricCard
              label="Total Demand"
              baseline={formatNumber(baseM.total_demand)}
              disrupted={formatNumber(disM.total_demand)}
              deltaText={`${comp.demand_delta >= 0 ? '+' : ''}${formatNumber(comp.demand_delta)}`}
              isWorse={comp.demand_delta > 0}
            />
            <ComparisonMetricCard
              label="Total Allocated"
              baseline={formatNumber(baseM.total_allocated)}
              disrupted={formatNumber(disM.total_allocated)}
              deltaText={`${comp.allocated_delta >= 0 ? '+' : ''}${formatNumber(comp.allocated_delta)}`}
              isWorse={comp.allocated_delta < 0}
            />
            <ComparisonMetricCard
              label="Unmet Demand"
              baseline={formatNumber(baseM.total_unmet_demand)}
              disrupted={formatNumber(disM.total_unmet_demand)}
              deltaText={`${comp.unmet_demand_delta >= 0 ? '+' : ''}${formatNumber(comp.unmet_demand_delta)}`}
              isWorse={comp.unmet_demand_delta > 0}
              negativeIsGood
            />
            <ComparisonMetricCard
              label="Critical Fulfillment"
              baseline={formatPercent(baseM.critical_fulfillment_pct)}
              disrupted={formatPercent(disM.critical_fulfillment_pct)}
              deltaText={`${comp.critical_fulfillment_delta >= 0 ? '+' : ''}${comp.critical_fulfillment_delta}%`}
              isWorse={comp.critical_fulfillment_delta < 0}
            />
            <ComparisonMetricCard
              label="High Fulfillment"
              baseline={formatPercent(baseM.high_fulfillment_pct)}
              disrupted={formatPercent(disM.high_fulfillment_pct)}
              deltaText={`${comp.high_fulfillment_delta >= 0 ? '+' : ''}${comp.high_fulfillment_delta}%`}
              isWorse={comp.high_fulfillment_delta < 0}
            />
            <ComparisonMetricCard
              label="Normal Fulfillment"
              baseline={formatPercent(baseM.normal_fulfillment_pct)}
              disrupted={formatPercent(disM.normal_fulfillment_pct)}
              deltaText={`${comp.normal_fulfillment_delta >= 0 ? '+' : ''}${comp.normal_fulfillment_delta}%`}
              isWorse={comp.normal_fulfillment_delta < 0}
            />
            <ComparisonMetricCard
              label="Transport Cost"
              baseline={formatCurrencyINR(baseM.total_transport_cost)}
              disrupted={formatCurrencyINR(disM.total_transport_cost)}
              deltaText={`${comp.transport_cost_delta >= 0 ? '+' : ''}₹${Math.abs(comp.transport_cost_delta).toLocaleString('en-IN')}`}
              isWorse={comp.transport_cost_delta > 0}
            />
            <ComparisonMetricCard
              label="Est. Route Distance"
              baseline={`${baseM.total_route_distance_km} km`}
              disrupted={`${disM.total_route_distance_km} km`}
              deltaText={`${comp.route_distance_km_delta >= 0 ? '+' : ''}${comp.route_distance_km_delta} km`}
              isWorse={comp.route_distance_km_delta > 0}
            />
            <ComparisonMetricCard
              label="Est. Route Duration"
              baseline={`${baseM.estimated_route_duration_min} min`}
              disrupted={`${disM.estimated_route_duration_min} min`}
              deltaText={`${
                (comp.route_duration_min_delta ??
                  Number((disM.estimated_route_duration_min - baseM.estimated_route_duration_min).toFixed(1))) >= 0
                  ? '+'
                  : ''
              }${
                comp.route_duration_min_delta ??
                Number((disM.estimated_route_duration_min - baseM.estimated_route_duration_min).toFixed(1))
              } min`}
              isWorse={
                (comp.route_duration_min_delta ??
                  disM.estimated_route_duration_min - baseM.estimated_route_duration_min) > 0
              }
            />
            <ComparisonMetricCard
              label="Available Vehicles"
              baseline={formatNumber(baseM.available_vehicles_count)}
              disrupted={formatNumber(disM.available_vehicles_count)}
              deltaText={`${comp.available_vehicles_delta >= 0 ? '+' : ''}${comp.available_vehicles_delta}`}
              isWorse={comp.available_vehicles_delta < 0}
            />
            <ComparisonMetricCard
              label="Feasible Vehicle Routes"
              baseline={formatNumber(baseM.completed_feasible_routes)}
              disrupted={formatNumber(disM.completed_feasible_routes)}
              deltaText={`${comp.completed_routes_delta >= 0 ? '+' : ''}${comp.completed_routes_delta}`}
              isWorse={disM.routing_status !== 'Optimal'}
            />
          </div>

          {/* Comparison Charts */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <h4 className="mb-3 text-sm font-semibold text-slate-900">
                Priority-Tier Fulfillment: Baseline vs. Disrupted (%)
              </h4>
              <div className="h-64 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={tierChartData} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="tier" tick={{ fontSize: 11 }} />
                    <YAxis domain={[0, 100]} unit="%" tick={{ fontSize: 11 }} />
                    <Tooltip formatter={(val) => `${Number(val).toFixed(2)}%`} />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    <Bar dataKey="Baseline" fill="#0d9488" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="Disrupted" fill="#dc2626" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <h4 className="mb-3 text-sm font-semibold text-slate-900">
                Network Volume Impact: Demand, Allocation &amp; Shortage
              </h4>
              <div className="h-64 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={volumeChartData} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="metric" tick={{ fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }} />
                    <Tooltip />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    <Bar dataKey="Baseline" fill="#132240" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="Disrupted" fill="#f97316" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
