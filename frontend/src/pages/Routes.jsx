import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  Eye,
  History,
  Map as MapIcon,
  Navigation,
  Package,
  Play,
  RefreshCw,
  Route as RouteIcon,
  Truck,
} from 'lucide-react';
import PageHeader from '../components/common/PageHeader';
import StatCard from '../components/common/StatCard';
import StatusBadge from '../components/common/StatusBadge';
import DataTable from '../components/tables/DataTable';
import ConfirmDialog from '../components/common/ConfirmDialog';
import PuneNetworkMap from '../components/maps/PuneNetworkMap';
import RoadNetworkPanel from '../components/routes/RoadNetworkPanel';
import { useToast } from '../components/common/ToastContext';
import { routeService } from '../services/routeService';
import { optimizationService } from '../services/optimizationService';
import { warehouseService } from '../services/warehouseService';
import { hospitalService } from '../services/hospitalService';
import {
  extractApiError,
  formatCurrencyINR,
  formatNumber,
  formatPercent,
} from '../utils/formatters';

const NEXT_STATUS_ACTIONS = {
  planned: [
    { status: 'dispatched', label: 'Dispatch Fleet', style: 'bg-teal-600 text-white hover:bg-teal-700' },
    { status: 'cancelled', label: 'Cancel Plan', style: 'border border-red-300 bg-white text-red-700 hover:bg-red-50' },
  ],
  dispatched: [
    { status: 'in_transit', label: 'Mark In Transit', style: 'bg-sky-600 text-white hover:bg-sky-700' },
    { status: 'delivered', label: 'Mark All Delivered', style: 'bg-emerald-600 text-white hover:bg-emerald-700' },
    { status: 'cancelled', label: 'Cancel', style: 'border border-red-300 bg-white text-red-700 hover:bg-red-50' },
  ],
  in_transit: [
    { status: 'partially_delivered', label: 'Partially Delivered', style: 'bg-orange-500 text-white hover:bg-orange-600' },
    { status: 'delivered', label: 'Mark All Delivered', style: 'bg-emerald-600 text-white hover:bg-emerald-700' },
    { status: 'cancelled', label: 'Cancel', style: 'border border-red-300 bg-white text-red-700 hover:bg-red-50' },
  ],
  partially_delivered: [
    { status: 'delivered', label: 'Complete Remaining', style: 'bg-emerald-600 text-white hover:bg-emerald-700' },
    { status: 'cancelled', label: 'Cancel Remaining', style: 'border border-red-300 bg-white text-red-700 hover:bg-red-50' },
  ],
  delivered: [],
  cancelled: [],
};

const STOP_NEXT_STATUSES = {
  planned: ['dispatched', 'cancelled'],
  dispatched: ['in_transit', 'partially_delivered', 'delivered', 'cancelled'],
  in_transit: ['partially_delivered', 'delivered', 'cancelled'],
  partially_delivered: ['delivered', 'cancelled'],
  delivered: [],
  cancelled: [],
};

const TABS = [
  { id: 'dispatch', label: 'Vehicle Assignments & Stops', icon: Truck },
  { id: 'map', label: 'Route Map View', icon: MapIcon },
  { id: 'history', label: 'Dispatch History', icon: History },
  { id: 'fleet', label: 'Fleet Vehicles', icon: Navigation },
  { id: 'corridors', label: 'Road Network & Corridors', icon: RouteIcon },
];

export default function RoutesPage() {
  const toast = useToast();

  // Base network & history data
  const [warehouses, setWarehouses] = useState([]);
  const [hospitals, setHospitals] = useState([]);
  const [corridors, setCorridors] = useState([]);
  const [vehicles, setVehicles] = useState([]);
  const [optRuns, setOptRuns] = useState([]);
  const [dispatchPlans, setDispatchPlans] = useState([]);
  const [activePlan, setActivePlan] = useState(null);
  const [roadNetworkStatus, setRoadNetworkStatus] = useState(null);

  // Generation controls
  const [selectedRunId, setSelectedRunId] = useState('');
  const [routingObjective, setRoutingObjective] = useState('min_distance');
  const [closedWayIdsInput, setClosedWayIdsInput] = useState('');
  const [allowMultiTrip, setAllowMultiTrip] = useState(true);
  const [allowSplitDeliveries, setAllowSplitDeliveries] = useState(true);

  // UI states
  const [activeTab, setActiveTab] = useState('dispatch');
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [updatingStatus, setUpdatingStatus] = useState(false);
  const [pendingPlanStatus, setPendingPlanStatus] = useState(null);
  const [error, setError] = useState(null);

  const loadAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [whRows, hospRows, corRows, vehRows, runRows, planRows, netStatus] = await Promise.all([
        warehouseService.list(),
        hospitalService.list(),
        routeService.listCorridors(),
        routeService.listVehicles(),
        optimizationService.listRuns(),
        routeService.listDispatchPlans(),
        routeService.getRoadNetworkStatus().catch(() => null),
      ]);
      setWarehouses(whRows);
      setHospitals(hospRows);
      setCorridors(corRows);
      setVehicles(vehRows);
      setRoadNetworkStatus(netStatus);
      const optimalRuns = runRows.filter((r) => r.solver_status === 'Optimal');
      setOptRuns(optimalRuns);
      setDispatchPlans(planRows);

      if (optimalRuns.length > 0) {
        setSelectedRunId((prev) => prev || String(optimalRuns[0].id));
      }

      if (planRows.length > 0) {
        setActivePlan((prev) => {
          if (prev) return prev;
          routeService
            .getDispatchPlan(planRows[0].id)
            .then(setActivePlan)
            .catch(() => {});
          return prev;
        });
      }
    } catch (err) {
      setError(extractApiError(err, 'Unable to load routes and dispatch data from backend API.'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  async function handleGenerateRoutes() {
    if (!selectedRunId) {
      toast.warning('Select optimization run', 'Run an optimization first before generating routes.');
      return;
    }
    const parsedClosedWays = closedWayIdsInput
      .split(/[,\s]+/)
      .map((token) => token.trim())
      .filter(Boolean)
      .map((token) => Number(token))
      .filter((num) => Number.isInteger(num) && num > 0);

    setGenerating(true);
    setError(null);
    try {
      const plan = await routeService.generateDispatchPlan({
        optimization_run_id: Number(selectedRunId),
        routing_objective: routingObjective,
        closed_way_ids: parsedClosedWays,
        allow_multi_trip: allowMultiTrip,
        max_trips_per_vehicle: 3,
        allow_split_deliveries: allowSplitDeliveries,
      });
      setActivePlan(plan);
      const updatedPlans = await routeService.listDispatchPlans();
      setDispatchPlans(updatedPlans);
      setActiveTab('dispatch');
      const sourceText = plan.routing_source === 'osm' ? 'OSM road geometry' : 'synthetic fallback';
      toast.success(
        'Dispatch plan generated',
        `${plan.plan_code} (${sourceText}): ${plan.total_routes} route(s), ${plan.total_stops} stop(s), ${plan.total_distance_km} km.`
      );
    } catch (err) {
      const msg = extractApiError(err, 'Failed to generate OR-Tools vehicle routes.');
      setError(msg);
      toast.error('Routing failed', msg);
    } finally {
      setGenerating(false);
    }
  }

  async function handleInspectPlan(planId) {
    try {
      const detail = await routeService.getDispatchPlan(planId);
      setActivePlan(detail);
      setActiveTab('dispatch');
      toast.info('Dispatch plan loaded', `Inspecting ${detail.plan_code}.`);
    } catch (err) {
      toast.error('Load failed', extractApiError(err, 'Could not load dispatch plan.'));
    }
  }

  async function handleConfirmPlanStatusChange() {
    if (!activePlan || !pendingPlanStatus) return;
    setUpdatingStatus(true);
    try {
      const updated = await routeService.updatePlanStatus(activePlan.id, pendingPlanStatus);
      setActivePlan(updated);
      const updatedPlans = await routeService.listDispatchPlans();
      setDispatchPlans(updatedPlans);
      toast.success(
        'Dispatch status updated',
        `${updated.plan_code} is now ${updated.status.replace(/_/g, ' ')}.`
      );
    } catch (err) {
      toast.error('Status update rejected', extractApiError(err, 'Invalid status transition.'));
    } finally {
      setUpdatingStatus(false);
      setPendingPlanStatus(null);
    }
  }

  async function handleStopStatusChange(stopId, newStatus) {
    if (!newStatus) return;
    setUpdatingStatus(true);
    try {
      const updatedPlan = await routeService.updateStopStatus(stopId, newStatus);
      setActivePlan(updatedPlan);
      const updatedPlans = await routeService.listDispatchPlans();
      setDispatchPlans(updatedPlans);
      toast.success('Stop status updated', `Stop marked as ${newStatus.replace(/_/g, ' ')}.`);
    } catch (err) {
      toast.error('Stop update failed', extractApiError(err, 'Invalid stop status transition.'));
    } finally {
      setUpdatingStatus(false);
    }
  }

  const closedCorridorMapLines = useMemo(() => {
    const closedCodes = new Set(activePlan?.closed_route_codes || []);
    return corridors
      .filter((c) => !c.is_available || closedCodes.has(c.route_code))
      .filter((c) => c.warehouse_lat && c.hospital_lat)
      .map((c) => ({
        route_code: c.route_code,
        warehouse_code: c.warehouse_code,
        hospital_code: c.hospital_code,
        distance_km: c.distance_km,
        from_lat: c.warehouse_lat,
        from_lon: c.warehouse_lon,
        to_lat: c.hospital_lat,
        to_lon: c.hospital_lon,
      }));
  }, [corridors, activePlan]);

  const assignmentColumns = [
    {
      key: 'vehicle_code',
      header: 'Assigned Vehicle',
      sortable: true,
      render: (r) => (
        <div>
          <span className="font-bold text-slate-900">{r.vehicle_code}</span>
          <p className="text-[11px] text-slate-500">
            {r.vehicle_type.replace(/_/g, ' ')} &bull; Wave #{r.trip_number}
          </p>
        </div>
      ),
    },
    {
      key: 'warehouse_code',
      header: 'Source Warehouse',
      sortable: true,
      render: (r) => (
        <div>
          <span className="font-semibold text-teal-800">{r.warehouse_code}</span>
          <p className="max-w-[180px] truncate text-[11px] text-slate-500">{r.warehouse_name}</p>
        </div>
      ),
    },
    {
      key: 'stops_seq',
      header: 'Ordered Hospital Stops',
      render: (r) => (
        <div className="flex flex-wrap items-center gap-1 text-xs">
          {(r.delivery_stops || []).map((s, idx) => (
            <span key={s.id} className="inline-flex items-center gap-1">
              {idx > 0 && <span className="text-slate-400">&rarr;</span>}
              <span className="rounded bg-slate-100 px-1.5 py-0.5 font-semibold text-slate-800">
                #{s.stop_sequence} {s.hospital_code}
              </span>
            </span>
          ))}
        </div>
      ),
    },
    {
      key: 'total_load_kg',
      header: 'Payload / Capacity',
      sortable: true,
      render: (r) => (
        <div className="min-w-[130px] text-xs">
          <span className="font-semibold text-slate-900">
            {formatNumber(r.total_load_kg)} / {formatNumber(r.capacity_kg)} kg
          </span>
          <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
            <div
              className={`h-full rounded-full ${
                r.utilization_pct > 90 ? 'bg-orange-500' : 'bg-teal-600'
              }`}
              style={{ width: `${Math.min(100, r.utilization_pct)}%` }}
            />
          </div>
        </div>
      ),
    },
    {
      key: 'route_distance_km',
      header: 'Est. Distance / Time',
      sortable: true,
      render: (r) => (
        <div className="text-xs">
          <span className="font-semibold text-slate-900">{r.route_distance_km} km</span>
          <p className="text-[11px] text-slate-500">{r.estimated_duration_min} min (est.)</p>
        </div>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      sortable: true,
      render: (r) => <StatusBadge status={r.status} />,
    },
  ];

  const historyColumns = [
    {
      key: 'plan_code',
      header: 'Plan Code',
      sortable: true,
      render: (r) => (
        <div>
          <span className="font-semibold text-slate-900">{r.plan_code}</span>
          {activePlan?.id === r.id && (
            <span className="ml-2 rounded bg-teal-50 px-1.5 py-0.5 text-[10px] font-bold text-teal-700">
              Viewing
            </span>
          )}
        </div>
      ),
    },
    { key: 'optimization_run_code', header: 'Source LP Run', sortable: true },
    {
      key: 'status',
      header: 'Dispatch Status',
      sortable: true,
      render: (r) => <StatusBadge status={r.status} />,
    },
    {
      key: 'solver_status',
      header: 'VRP / Source',
      sortable: true,
      render: (r) => (
        <div className="flex flex-wrap items-center gap-1">
          <StatusBadge status={r.solver_status} />
          <span
            className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${
              r.routing_source === 'osm'
                ? 'bg-teal-50 text-teal-800'
                : 'bg-amber-50 text-amber-800'
            }`}
          >
            {r.routing_source === 'osm' ? 'OSM' : 'Fallback'}
          </span>
        </div>
      ),
    },
    {
      key: 'total_routes',
      header: 'Routes / Stops',
      sortable: true,
      render: (r) => `${r.total_routes} route(s) / ${r.total_stops} stop(s)`,
    },
    {
      key: 'total_distance_km',
      header: 'Est. Distance',
      sortable: true,
      render: (r) => `${r.total_distance_km} km (${r.estimated_duration_min} min)`,
    },
    {
      key: 'actions',
      header: 'Inspect',
      render: (r) => (
        <button
          type="button"
          onClick={() => handleInspectPlan(r.id)}
          className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-xs font-semibold text-slate-700 hover:border-teal-300 hover:bg-teal-50 hover:text-teal-700"
        >
          <Eye className="h-3.5 w-3.5" />
          Inspect
        </button>
      ),
    },
  ];

  const corridorColumns = [
    { key: 'route_code', header: 'Route ID', sortable: true },
    { key: 'warehouse_code', header: 'From Warehouse', sortable: true },
    { key: 'hospital_code', header: 'To Hospital', sortable: true },
    {
      key: 'distance_km',
      header: 'Est. Distance (km)',
      sortable: true,
      render: (r) => `${Number(r.distance_km).toFixed(2)} km`,
    },
    {
      key: 'estimated_travel_time_min',
      header: 'Est. Time (min)',
      sortable: true,
      render: (r) => `${Number(r.estimated_travel_time_min).toFixed(1)} min`,
    },
    {
      key: 'base_transport_cost_per_unit',
      header: 'Base Unit Cost',
      sortable: true,
      render: (r) => formatCurrencyINR(r.base_transport_cost_per_unit),
    },
    {
      key: 'is_available',
      header: 'Corridor',
      sortable: true,
      render: (r) => (
        <StatusBadge
          status={r.is_available ? 'active' : 'critical'}
          label={r.is_available ? 'Open' : 'Closed'}
        />
      ),
    },
  ];

  const vehicleColumns = [
    { key: 'vehicle_code', header: 'Vehicle Code', sortable: true },
    { key: 'warehouse_code', header: 'Home Depot', sortable: true },
    { key: 'warehouse_area', header: 'Locality', sortable: true },
    {
      key: 'vehicle_type',
      header: 'Vehicle Type',
      sortable: true,
      render: (r) => <span className="capitalize">{r.vehicle_type.replace(/_/g, ' ')}</span>,
    },
    {
      key: 'capacity_kg',
      header: 'Payload Capacity',
      sortable: true,
      render: (r) => `${formatNumber(r.capacity_kg)} kg`,
    },
    {
      key: 'status',
      header: 'Availability',
      sortable: true,
      render: (r) => <StatusBadge status={r.status === 'available' ? 'active' : 'inactive'} label={r.status} />,
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Vehicle Routing & Dispatch Management"
        badge="Google OR-Tools CVRP"
        description="Convert completed Phase 3 LP allocations into multi-depot capacitated vehicle routes, manage dispatch lifecycles, and track hospital stop deliveries."
        actions={
          <button
            type="button"
            onClick={loadAll}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        }
      />

      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-xs text-red-800">
          <strong>Routing Notice:</strong> {error}
        </div>
      )}

      {/* Route Generation Panel */}
      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="flex-1 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-sm font-bold text-slate-900">
                Generate Dispatch Plan from Completed Optimization Run
              </h2>
              {roadNetworkStatus && (
                <span
                  className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-semibold ${
                    roadNetworkStatus.osm_available
                      ? 'bg-teal-50 text-teal-800 ring-1 ring-teal-200'
                      : 'bg-amber-50 text-amber-800 ring-1 ring-amber-200'
                  }`}
                >
                  <span
                    className={`h-1.5 w-1.5 rounded-full ${
                      roadNetworkStatus.osm_available ? 'bg-teal-600' : 'bg-amber-500'
                    }`}
                  />
                  {roadNetworkStatus.osm_available
                    ? `OSM Road Graph Active (${formatNumber(roadNetworkStatus.node_count)} nodes / ${formatNumber(roadNetworkStatus.edge_count)} segments)`
                    : 'Synthetic Corridor Fallback Active'}
                </span>
              )}
            </div>

            <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
              <div>
                <label className="block text-xs font-semibold text-slate-700">
                  Source Optimization Run (Phase 3 LP Allocations)
                </label>
                <select
                  value={selectedRunId}
                  onChange={(e) => setSelectedRunId(e.target.value)}
                  className="mt-1 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs text-slate-900 focus:border-teal-600 focus:outline-none"
                >
                  {optRuns.length === 0 ? (
                    <option value="">No completed optimization runs — run Optimizer first</option>
                  ) : (
                    optRuns.map((run) => (
                      <option key={run.id} value={String(run.id)}>
                        {run.run_code} ({run.model_type === 'lexicographic_priority' ? 'Lexicographic Priority' : 'Transportation LP'}) — {formatNumber(run.total_allocated)} units
                      </option>
                    ))
                  )}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700">
                  Routing Objective
                </label>
                <select
                  value={routingObjective}
                  onChange={(e) => setRoutingObjective(e.target.value)}
                  className="mt-1 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs text-slate-900 focus:border-teal-600 focus:outline-none"
                >
                  <option value="min_distance">Minimum Road Distance (km)</option>
                  <option value="min_time">Minimum Estimated Travel Time (min)</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700">
                  Closed OSM Way IDs (Optional)
                </label>
                <input
                  type="text"
                  value={closedWayIdsInput}
                  onChange={(e) => setClosedWayIdsInput(e.target.value)}
                  placeholder="e.g., 210788741, 40581234"
                  className="mt-1 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs text-slate-900 focus:border-teal-600 focus:outline-none"
                />
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-xs text-slate-700">
              <label className="flex cursor-pointer items-center gap-2">
                <input
                  type="checkbox"
                  checked={allowMultiTrip}
                  onChange={(e) => setAllowMultiTrip(e.target.checked)}
                  className="rounded border-slate-300 text-teal-600 focus:ring-teal-600"
                />
                Allow multi-wave trips per vehicle (up to 3 closed tours/depot)
              </label>
              <label className="flex cursor-pointer items-center gap-2">
                <input
                  type="checkbox"
                  checked={allowSplitDeliveries}
                  onChange={(e) => setAllowSplitDeliveries(e.target.checked)}
                  className="rounded border-slate-300 text-teal-600 focus:ring-teal-600"
                />
                Allow split loads when a hospital shipment exceeds single-truck weight capacity
              </label>
            </div>
          </div>

          <button
            type="button"
            disabled={generating || !selectedRunId}
            onClick={handleGenerateRoutes}
            className="inline-flex shrink-0 items-center justify-center gap-2 rounded-lg bg-teal-600 px-5 py-2.5 text-xs font-semibold text-white shadow-sm hover:bg-teal-700 disabled:opacity-50"
          >
            <Play className="h-3.5 w-3.5" />
            {generating ? 'Solving OR-Tools VRP...' : 'Generate Vehicle Routes'}
          </button>
        </div>
        <p className="mt-3 text-[11px] text-slate-500">
          Each warehouse is solved independently as a depot CVRP using 1D weight capacity (kg) on{' '}
          <strong>&copy; OpenStreetMap contributors</strong> road geometry (with synthetic fallback if uncached).
          Estimated travel times use assumed highway-class speed profiles and do <strong>not</strong> represent live traffic or guaranteed arrival times.
          Generating a dispatch plan creates status <strong>Planned</strong> records only and never modifies live inventory or demand.
        </p>
      </div>

      {/* Active Dispatch Plan Header & Lifecycle Controls */}
      {activePlan && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white px-5 py-4 shadow-sm">
            <div className="flex flex-wrap items-center gap-2.5">
              <span className="rounded-md bg-navy-900 px-2.5 py-1 text-xs font-bold text-white">
                {activePlan.plan_code}
              </span>
              <StatusBadge status={activePlan.status} />
              <StatusBadge status={activePlan.solver_status} label={`VRP: ${activePlan.solver_status}`} />
              <span
                className={`rounded-full px-2.5 py-0.5 text-[11px] font-semibold ${
                  activePlan.routing_source === 'osm'
                    ? 'bg-teal-50 text-teal-800 ring-1 ring-teal-200'
                    : 'bg-amber-50 text-amber-800 ring-1 ring-amber-200'
                }`}
              >
                {activePlan.routing_source === 'osm' ? 'OSM Road Network' : 'Synthetic Fallback'}
              </span>
              <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-[11px] font-semibold text-slate-700">
                {activePlan.routing_objective === 'min_time'
                  ? 'Objective: Min Est. Time'
                  : 'Objective: Min Distance'}
              </span>
              <span className="text-xs text-slate-500">
                From LP Run: <strong>{activePlan.optimization_run_code}</strong>
              </span>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {(NEXT_STATUS_ACTIONS[activePlan.status] || []).map((act) => (
                <button
                  key={act.status}
                  type="button"
                  disabled={updatingStatus}
                  onClick={() => setPendingPlanStatus(act.status)}
                  className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition disabled:opacity-50 ${act.style}`}
                >
                  {act.label}
                </button>
              ))}
            </div>
          </div>

          {activePlan.fallback_warning && (
            <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs text-amber-900">
              <strong>Synthetic Fallback Active:</strong> {activePlan.fallback_warning}
            </div>
          )}

          {activePlan.unreachable_hospitals?.length > 0 && (
            <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-xs text-red-900">
              <strong>Unreachable Hospital(s):</strong>{' '}
              {activePlan.unreachable_hospitals.join(', ')} — excluded from routing rather than
              inventing synthetic paths under current road closures/restrictions.
            </div>
          )}

          {activePlan.infeasibility_reasons?.length > 0 && (
            <div className="rounded-xl border border-orange-200 bg-orange-50 px-4 py-3 text-xs text-orange-900">
              <div className="flex items-start gap-2">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-orange-600" />
                <div>
                  <p className="font-semibold">Routing Warnings / Partial Infeasibility:</p>
                  <ul className="mt-1 list-disc pl-4">
                    {activePlan.infeasibility_reasons.map((r) => (
                      <li key={r}>{r}</li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          )}

          {/* KPI Strip */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard
              title="Vehicle Routes"
              value={`${activePlan.total_routes} tour(s)`}
              subtitle={`${activePlan.total_vehicles_used} unique vehicle(s) assigned`}
              icon={Truck}
              accent="teal"
              sourceTag="OR-Tools CVRP"
            />
            <StatCard
              title="Delivery Stops"
              value={formatNumber(activePlan.total_stops)}
              subtitle="Ordered hospital deliveries"
              icon={CheckCircle2}
              accent="emerald"
              sourceTag="Multi-Stop"
            />
            <StatCard
              title={activePlan.routing_source === 'osm' ? 'Road Route Distance' : 'Est. Route Distance'}
              value={`${activePlan.total_distance_km} km`}
              subtitle={`Est. ${activePlan.estimated_duration_min} min (speed profile, not live traffic)`}
              icon={Clock}
              accent="slate"
              sourceTag={activePlan.routing_source === 'osm' ? 'OSM Road Graph' : 'Synthetic Fallback'}
            />
            <StatCard
              title="Total Payload Weight"
              value={`${formatNumber(activePlan.total_weight_kg)} kg`}
              subtitle="100% conserved from LP allocation"
              icon={Package}
              accent="teal"
              sourceTag="1D Weight Cap"
            />
          </div>
        </div>
      )}

      {/* Tabs */}
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
              {id === 'history' && (
                <span className="rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-600">
                  {dispatchPlans.length}
                </span>
              )}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab Content */}
      {activeTab === 'corridors' ? (
        <div className="space-y-6">
          <RoadNetworkPanel
            roadNetworkStatus={roadNetworkStatus}
            onStatusUpdated={setRoadNetworkStatus}
            warehouses={warehouses}
            hospitals={hospitals}
          />
          <div>
            <h3 className="mb-3 text-sm font-bold text-slate-900">
              Seeded Synthetic Warehouse-to-Hospital Corridors (Fallback Reference)
            </h3>
            <DataTable
              columns={corridorColumns}
              rows={corridors}
              loading={loading}
              defaultSortKey="route_code"
              emptyMessage="No road corridors found."
            />
          </div>
        </div>
      ) : activeTab === 'fleet' ? (
        <DataTable
          columns={vehicleColumns}
          rows={vehicles}
          loading={loading}
          defaultSortKey="vehicle_code"
          emptyMessage="No fleet vehicles found."
        />
      ) : activeTab === 'history' ? (
        <DataTable
          columns={historyColumns}
          rows={dispatchPlans}
          loading={loading}
          emptyMessage="No dispatch plans generated yet. Select an optimization run above and click 'Generate Vehicle Routes'."
        />
      ) : activeTab === 'map' ? (
        <PuneNetworkMap
          warehouses={warehouses}
          hospitals={hospitals}
          vehicleRoutes={activePlan?.vehicle_assignments || []}
          closedCorridors={closedCorridorMapLines}
          closedOsmWays={activePlan?.closed_osm_ways || []}
          unreachableHospitals={activePlan?.unreachable_hospitals || []}
          routingSource={activePlan?.routing_source || (roadNetworkStatus?.osm_available ? 'osm' : 'synthetic_fallback')}
          routingObjective={activePlan?.routing_objective || routingObjective}
          fallbackWarning={activePlan?.fallback_warning || null}
          title={
            activePlan
              ? `Dispatch Plan ${activePlan.plan_code} — Multi-Depot Vehicle Routes`
              : 'Pune & Pimpri-Chinchwad Medical Logistics Network'
          }
          heightClass="h-[480px]"
        />
      ) : !activePlan ? (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white p-10 text-center">
          <Truck className="mx-auto h-8 w-8 text-teal-600" />
          <h3 className="mt-3 text-sm font-bold text-slate-900">
            No Dispatch Plan Selected Yet
          </h3>
          <p className="mx-auto mt-1.5 max-w-xl text-xs text-slate-600">
            Select a completed Phase 3 optimization run above and click{' '}
            <strong>Generate Vehicle Routes</strong> to run Google OR-Tools CVRP per warehouse depot.
          </p>
        </div>
      ) : (
        <div className="space-y-6">
          {/* Vehicle Assignment Table */}
          <DataTable
            columns={assignmentColumns}
            rows={activePlan.vehicle_assignments || []}
            defaultSortKey="warehouse_code"
            emptyMessage="No vehicle assignments in this plan."
          />

          {/* Detailed Ordered Hospital Stops & Product Shipments */}
          <div className="space-y-4">
            <h3 className="text-sm font-bold text-slate-900">
              Ordered Delivery Stops &amp; Product-Wise Shipment Quantities
            </h3>
            {(activePlan.vehicle_assignments || []).map((va) => (
              <div
                key={va.id}
                className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm"
              >
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 bg-slate-50 px-5 py-3 text-xs">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded bg-navy-900 px-2 py-0.5 font-bold text-white">
                      {va.vehicle_code}
                    </span>
                    <span className="font-semibold text-slate-900">
                      Wave #{va.trip_number} &bull; Depot: {va.warehouse_code} ({va.warehouse_name})
                    </span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-slate-600">
                      Load: <strong>{va.total_load_kg} / {va.capacity_kg} kg</strong> (
                      {formatPercent(va.utilization_pct)})
                    </span>
                    <span className="text-slate-600">
                      Est: <strong>{va.route_distance_km} km</strong> &bull; {va.estimated_duration_min} min
                    </span>
                    <StatusBadge status={va.status} />
                  </div>
                </div>

                <div className="divide-y divide-slate-100">
                  {(va.delivery_stops || []).map((stop) => {
                    const nextOpts = STOP_NEXT_STATUSES[stop.status] || [];
                    return (
                      <div key={stop.id} className="p-4">
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div>
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="flex h-6 w-6 items-center justify-center rounded-full bg-teal-600 text-xs font-bold text-white">
                                {stop.stop_sequence}
                              </span>
                              <span className="text-sm font-bold text-slate-900">
                                {stop.hospital_code} — {stop.hospital_name}
                              </span>
                              <StatusBadge status={stop.priority_level} />
                              <StatusBadge status={stop.status} />
                            </div>
                            <p className="mt-1 pl-8 text-xs text-slate-500">
                              Area: {stop.hospital_area} &bull; Leg: {stop.leg_distance_km} km &bull;
                              ETA: {stop.estimated_arrival_min} min (est.) &bull; Stop Weight:{' '}
                              <strong>{stop.stop_weight_kg} kg</strong>
                            </p>
                          </div>

                          {nextOpts.length > 0 && (
                            <div className="flex items-center gap-2">
                              <select
                                aria-label={`Update stop status for ${stop.hospital_code}`}
                                defaultValue=""
                                disabled={updatingStatus}
                                onChange={(e) => {
                                  if (e.target.value) {
                                    handleStopStatusChange(stop.id, e.target.value);
                                    e.target.value = '';
                                  }
                                }}
                                className="rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs font-semibold text-slate-700 focus:border-teal-600 focus:outline-none disabled:opacity-50"
                              >
                                <option value="">Update Stop Status...</option>
                                {nextOpts.map((st) => (
                                  <option key={st} value={st}>
                                    Mark {st.replace(/_/g, ' ')}
                                  </option>
                                ))}
                              </select>
                            </div>
                          )}
                        </div>

                        {/* Product Shipment Lines */}
                        <div className="mt-3 ml-8 grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4">
                          {(stop.shipment_lines || []).map((line) => (
                            <div
                              key={line.id}
                              className="rounded-lg border border-slate-200 bg-slate-50/70 px-3 py-2 text-xs"
                            >
                              <p className="font-semibold text-slate-900">
                                {line.product_name}{' '}
                                <span className="text-[10px] text-slate-400">({line.product_code})</span>
                              </p>
                              <p className="mt-1 text-slate-700">
                                Planned: <strong>{formatNumber(line.quantity_planned)}</strong> {line.unit}
                              </p>
                              <p className="text-[11px] text-slate-500">
                                Delivered:{' '}
                                <strong className={line.quantity_delivered > 0 ? 'text-emerald-700' : ''}>
                                  {formatNumber(line.quantity_delivered)}
                                </strong>{' '}
                                &bull; {line.total_weight_kg} kg
                              </p>
                            </div>
                          ))}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Plan Status Transition Confirmation */}
      <ConfirmDialog
        open={Boolean(pendingPlanStatus)}
        onClose={() => setPendingPlanStatus(null)}
        onConfirm={handleConfirmPlanStatusChange}
        loading={updatingStatus}
        tone={pendingPlanStatus === 'cancelled' ? 'danger' : 'primary'}
        title="Confirm Dispatch Status Update"
        confirmLabel="Confirm Status Change"
        message={
          activePlan && pendingPlanStatus
            ? `Transition dispatch plan ${activePlan.plan_code} from '${activePlan.status.replace(
                /_/g,
                ' '
              )}' to '${pendingPlanStatus.replace(/_/g, ' ')}'?`
            : ''
        }
      />
    </div>
  );
}
