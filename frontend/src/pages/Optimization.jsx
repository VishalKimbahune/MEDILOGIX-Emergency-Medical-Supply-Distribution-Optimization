import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Activity,
  AlertTriangle,
  BarChart3,
  BookOpen,
  CheckCircle2,
  Clock,
  Cpu,
  Eye,
  GitCompare,
  History,
  IndianRupee,
  Play,
  RefreshCw,
  Search,
  Table2,
  TrendingUp,
} from 'lucide-react';
import PageHeader from '../components/common/PageHeader';
import StatCard from '../components/common/StatCard';
import StatusBadge from '../components/common/StatusBadge';
import DataTable from '../components/tables/DataTable';
import OptimizationCharts from '../components/charts/OptimizationCharts';
import MathematicalExplanationPanel from '../components/optimization/MathematicalExplanationPanel';
import ModelComparisonPanel from '../components/optimization/ModelComparisonPanel';
import { useToast } from '../components/common/ToastContext';
import { optimizationService } from '../services/optimizationService';
import { warehouseService } from '../services/warehouseService';
import { hospitalService } from '../services/hospitalService';
import { inventoryService } from '../services/inventoryService';
import { demandService } from '../services/demandService';
import {
  extractApiError,
  formatCurrencyINR,
  formatNumber,
  formatPercent,
} from '../utils/formatters';

const TABS = [
  { id: 'overview', label: 'Priority & Overview', icon: Activity },
  { id: 'allocations', label: 'Allocation Table', icon: Table2 },
  { id: 'charts', label: 'Visual Analytics', icon: BarChart3 },
  { id: 'math', label: 'Mathematical Model', icon: BookOpen },
  { id: 'compare', label: 'Model Comparison', icon: GitCompare },
  { id: 'history', label: 'Run History', icon: History },
];

export default function Optimization() {
  const toast = useToast();

  // Live network context
  const [warehouses, setWarehouses] = useState([]);
  const [hospitals, setHospitals] = useState([]);
  const [products, setProducts] = useState([]);
  const [demands, setDemands] = useState([]);
  const [runs, setRuns] = useState([]);
  const [loadingContext, setLoadingContext] = useState(true);

  // Configuration controls
  const [method, setMethod] = useState('lexicographic_priority');
  const [selectedWarehouses, setSelectedWarehouses] = useState([]);
  const [selectedHospitals, setSelectedHospitals] = useState([]);
  const [selectedProducts, setSelectedProducts] = useState([]);
  const [enforceRouteAvailability, setEnforceRouteAvailability] = useState(true);
  const [allowUnmetDemand, setAllowUnmetDemand] = useState(true);

  // Execution & Inspection states
  const [running, setRunning] = useState(false);
  const [comparing, setComparing] = useState(false);
  const [loadingHistoryDetail, setLoadingHistoryDetail] = useState(false);
  const [activeResult, setActiveResult] = useState(null);
  const [comparison, setComparison] = useState(null);
  const [activeTab, setActiveTab] = useState('overview');
  const [error, setError] = useState(null);

  // Allocation table filters
  const [allocSearch, setAllocSearch] = useState('');
  const [allocWhFilter, setAllocWhFilter] = useState('all');
  const [allocProdFilter, setAllocProdFilter] = useState('all');
  const [allocPrioFilter, setAllocPrioFilter] = useState('all');

  const loadContext = useCallback(async () => {
    setLoadingContext(true);
    try {
      const [whRows, hospRows, prodRows, demRows, runRows] = await Promise.all([
        warehouseService.list(),
        hospitalService.list(),
        inventoryService.listProducts(),
        demandService.list(),
        optimizationService.listRuns(),
      ]);
      const activeWh = whRows.filter((w) => w.status === 'active');
      const activeHosp = hospRows.filter((h) => h.status === 'active');
      setWarehouses(activeWh);
      setHospitals(activeHosp);
      setProducts(prodRows);
      setDemands(demRows);
      setRuns(runRows);

      // Select all active entities by default on first load
      setSelectedWarehouses((prev) =>
        prev.length > 0 ? prev : activeWh.map((w) => w.code)
      );
      setSelectedHospitals((prev) =>
        prev.length > 0 ? prev : activeHosp.map((h) => h.code)
      );
      setSelectedProducts((prev) =>
        prev.length > 0 ? prev : prodRows.map((p) => p.code)
      );

      // Automatically inspect the latest persisted run if none is currently displayed
      if (runRows.length > 0) {
        setActiveResult((current) => {
          if (current) return current;
          optimizationService
            .getRunDetail(runRows[0].id)
            .then((detail) => setActiveResult(detail))
            .catch(() => {});
          return current;
        });
      }
    } catch (err) {
      setError(
        extractApiError(
          err,
          'Unable to load network context from FastAPI backend. Start uvicorn on port 8000.'
        )
      );
    } finally {
      setLoadingContext(false);
    }
  }, []);

  useEffect(() => {
    loadContext();
  }, [loadContext]);

  const actionableDemands = useMemo(
    () => demands.filter((d) => d.status === 'open' || d.status === 'partially_fulfilled'),
    [demands]
  );

  const openDemandCount = actionableDemands.length;

  const openDemandUnits = useMemo(
    () =>
      actionableDemands.reduce((sum, d) => sum + Number(d.quantity_requested || 0), 0),
    [actionableDemands]
  );

  const selectedScopeDemandUnits = useMemo(() => {
    const selectedHospIds = new Set(
      hospitals.filter((h) => selectedHospitals.includes(h.code)).map((h) => h.id)
    );
    const selectedProdIds = new Set(
      products.filter((p) => selectedProducts.includes(p.code)).map((p) => p.id)
    );
    return actionableDemands
      .filter((d) => selectedHospIds.has(d.hospital_id) && selectedProdIds.has(d.product_id))
      .reduce((sum, d) => sum + Number(d.quantity_requested || 0), 0);
  }, [actionableDemands, hospitals, products, selectedHospitals, selectedProducts]);

  function toggleSelection(code, currentList, setter) {
    if (currentList.includes(code)) {
      setter(currentList.filter((item) => item !== code));
    } else {
      setter([...currentList, code]);
    }
  }

  function buildRequestPayload() {
    return {
      model_type: method,
      warehouse_codes:
        selectedWarehouses.length > 0 && selectedWarehouses.length < warehouses.length
          ? selectedWarehouses
          : null,
      hospital_codes:
        selectedHospitals.length > 0 && selectedHospitals.length < hospitals.length
          ? selectedHospitals
          : null,
      product_codes:
        selectedProducts.length > 0 && selectedProducts.length < products.length
          ? selectedProducts
          : null,
      enforce_route_availability: enforceRouteAvailability,
      allow_unmet_demand: method === 'transportation_lp' ? allowUnmetDemand : true,
    };
  }

  async function handleRunOptimization() {
    if (selectedWarehouses.length === 0 || selectedHospitals.length === 0 || selectedProducts.length === 0) {
      const msg = 'Select at least one warehouse, hospital, and medical product before solving.';
      setError(msg);
      toast.warning('Invalid selection', msg);
      return;
    }

    setRunning(true);
    setError(null);
    try {
      const payload = buildRequestPayload();
      const data =
        method === 'lexicographic_priority'
          ? await optimizationService.runLexicographicPriority(payload)
          : await optimizationService.runTransportation(payload);

      setActiveResult(data);
      const updatedRuns = await optimizationService.listRuns();
      setRuns(updatedRuns);

      if (data.solver_status === 'Optimal') {
        toast.success(
          'Optimization completed (Optimal)',
          `${data.run_code}: ${formatPercent(data.fulfillment_percentage)} fulfilled at ${formatCurrencyINR(
            data.total_cost
          )}.`
        );
      } else {
        toast.warning(
          `Solver finished: ${data.solver_status}`,
          'No optimal allocation found under current constraints.'
        );
      }
      if (activeTab === 'history' || activeTab === 'compare') {
        setActiveTab('overview');
      }
    } catch (err) {
      const msg = extractApiError(err, 'Failed to execute optimization solver.');
      setError(msg);
      toast.error('Optimization failed', msg);
    } finally {
      setRunning(false);
    }
  }

  async function handleCompareModels() {
    if (selectedWarehouses.length === 0 || selectedHospitals.length === 0 || selectedProducts.length === 0) {
      const msg = 'Select at least one warehouse, hospital, and medical product before comparing.';
      setError(msg);
      toast.warning('Invalid selection', msg);
      return;
    }

    setComparing(true);
    setError(null);
    try {
      const payload = {
        ...buildRequestPayload(),
        allow_unmet_demand: true,
      };
      const compData = await optimizationService.compareModels(payload);
      setComparison(compData);
      setActiveResult(compData.lexicographic_priority);
      const updatedRuns = await optimizationService.listRuns();
      setRuns(updatedRuns);
      setActiveTab('compare');
      toast.success(
        'Comparison complete',
        'Both Transportation LP and Lexicographic Priority models solved and persisted.'
      );
    } catch (err) {
      const msg = extractApiError(err, 'Failed to run model comparison.');
      setError(msg);
      toast.error('Comparison failed', msg);
    } finally {
      setComparing(false);
    }
  }

  async function handleInspectRun(runId) {
    setLoadingHistoryDetail(true);
    setError(null);
    try {
      const detail = await optimizationService.getRunDetail(runId);
      setActiveResult(detail);
      setActiveTab('overview');
      toast.info('Historical run loaded', `Inspecting ${detail.run_code} (${detail.model_type}).`);
    } catch (err) {
      const msg = extractApiError(err, 'Could not load historical optimization run.');
      toast.error('Load failed', msg);
    } finally {
      setLoadingHistoryDetail(false);
    }
  }

  const filteredAllocations = useMemo(() => {
    const rows = activeResult?.allocations || [];
    const q = allocSearch.trim().toLowerCase();
    return rows.filter((row) => {
      if (allocWhFilter !== 'all' && row.warehouse_code !== allocWhFilter) return false;
      if (allocProdFilter !== 'all' && row.product_code !== allocProdFilter) return false;
      if (allocPrioFilter !== 'all' && row.hospital_priority !== allocPrioFilter) return false;
      if (!q) return true;
      return (
        row.warehouse_code.toLowerCase().includes(q) ||
        row.hospital_code.toLowerCase().includes(q) ||
        (row.hospital_name || '').toLowerCase().includes(q) ||
        row.product_code.toLowerCase().includes(q) ||
        (row.product_name || '').toLowerCase().includes(q) ||
        (row.route_code || '').toLowerCase().includes(q)
      );
    });
  }, [activeResult, allocSearch, allocWhFilter, allocProdFilter, allocPrioFilter]);

  const allocationColumns = [
    {
      key: 'warehouse_code',
      header: 'Warehouse',
      sortable: true,
      render: (r) => (
        <div>
          <span className="font-semibold text-slate-900">{r.warehouse_code}</span>
          {r.warehouse_name && (
            <p className="max-w-[180px] truncate text-[11px] text-slate-500">
              {r.warehouse_name}
            </p>
          )}
        </div>
      ),
    },
    {
      key: 'hospital_code',
      header: 'Hospital',
      sortable: true,
      render: (r) => (
        <div>
          <div className="flex items-center gap-1.5">
            <span className="font-semibold text-slate-900">{r.hospital_code}</span>
            {r.hospital_priority && <StatusBadge status={r.hospital_priority} />}
          </div>
          {r.hospital_name && (
            <p className="max-w-[200px] truncate text-[11px] text-slate-500">
              {r.hospital_name}
            </p>
          )}
        </div>
      ),
    },
    {
      key: 'product_code',
      header: 'Product',
      sortable: true,
      render: (r) => (
        <div>
          <span className="font-medium text-slate-900">{r.product_name || r.product_code}</span>
          <span className="ml-1 text-xs text-slate-400">({r.product_code})</span>
        </div>
      ),
    },
    {
      key: 'quantity_allocated',
      header: 'Allocated Qty',
      sortable: true,
      render: (r) => (
        <span className="font-bold text-teal-700">
          {formatNumber(r.quantity_allocated)}{' '}
          <span className="text-xs font-normal text-slate-500">{r.product_unit || 'units'}</span>
        </span>
      ),
    },
    {
      key: 'transport_cost',
      header: 'Transport Cost',
      sortable: true,
      render: (r) => (
        <div>
          <span className="font-semibold text-slate-900">
            {formatCurrencyINR(r.transport_cost)}
          </span>
          <p className="text-[11px] text-slate-500">
            {formatCurrencyINR(r.unit_cost)} / unit
          </p>
        </div>
      ),
    },
    {
      key: 'route_code',
      header: 'Route Info',
      sortable: true,
      render: (r) =>
        r.route_code ? (
          <div className="text-xs">
            <span className="font-semibold text-slate-800">{r.route_code}</span>
            <p className="text-[11px] text-slate-500">
              {r.distance_km} km &bull; {r.estimated_travel_time_min} min (est.)
            </p>
          </div>
        ) : (
          <span className="text-xs text-slate-400">—</span>
        ),
    },
  ];

  const hospitalSummaryColumns = [
    { key: 'hospital_code', header: 'Hospital', sortable: true },
    {
      key: 'priority_level',
      header: 'Priority',
      sortable: true,
      render: (r) => <StatusBadge status={r.priority_level} />,
    },
    {
      key: 'total_demand',
      header: 'Total Demand',
      sortable: true,
      render: (r) => formatNumber(r.total_demand),
    },
    {
      key: 'total_allocated',
      header: 'Planned Allocation',
      sortable: true,
      render: (r) => <span className="font-semibold text-emerald-700">{formatNumber(r.total_allocated)}</span>,
    },
    {
      key: 'total_unmet',
      header: 'Unmet Shortage',
      sortable: true,
      render: (r) => (
        <span className={r.total_unmet > 0 ? 'font-semibold text-red-600' : 'text-slate-500'}>
          {formatNumber(r.total_unmet)}
        </span>
      ),
    },
    {
      key: 'fulfillment_pct',
      header: 'Fulfillment %',
      sortable: true,
      render: (r) => formatPercent(r.fulfillment_pct),
    },
    {
      key: 'transport_cost',
      header: 'Transport Cost',
      sortable: true,
      render: (r) => formatCurrencyINR(r.transport_cost),
    },
  ];

  const historyColumns = [
    {
      key: 'run_code',
      header: 'Run Code',
      sortable: true,
      render: (r) => (
        <div>
          <span className="font-semibold text-slate-900">{r.run_code}</span>
          {activeResult?.id === r.id && (
            <span className="ml-2 rounded bg-teal-50 px-1.5 py-0.5 text-[10px] font-bold text-teal-700">
              Viewing
            </span>
          )}
        </div>
      ),
    },
    {
      key: 'model_type',
      header: 'Optimization Model',
      sortable: true,
      render: (r) =>
        r.model_type === 'lexicographic_priority'
          ? 'Lexicographic Priority (4-Stage)'
          : 'Transportation Cost LP',
    },
    {
      key: 'solver_status',
      header: 'Status',
      sortable: true,
      render: (r) => <StatusBadge status={r.solver_status} />,
    },
    {
      key: 'total_allocated',
      header: 'Allocated / Unmet',
      sortable: true,
      render: (r) =>
        `${formatNumber(r.total_allocated)} / ${formatNumber(r.total_unmet_demand)}`,
    },
    {
      key: 'total_cost',
      header: 'Transport Cost',
      sortable: true,
      render: (r) => formatCurrencyINR(r.total_cost),
    },
    {
      key: 'execution_time_ms',
      header: 'Time',
      sortable: true,
      render: (r) => `${r.execution_time_ms} ms`,
    },
    {
      key: 'actions',
      header: 'Inspect',
      render: (r) => (
        <button
          type="button"
          disabled={loadingHistoryDetail}
          onClick={() => handleInspectRun(r.id)}
          className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-xs font-semibold text-slate-700 hover:border-teal-300 hover:bg-teal-50 hover:text-teal-700 disabled:opacity-50"
        >
          <Eye className="h-3.5 w-3.5" />
          Inspect
        </button>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Operations Research Optimization Engine"
        badge="PuLP CBC Solver"
        description="Configure and execute Multi-Commodity Transportation LP or Sequential 4-Stage Lexicographic Priority Shortage Optimization."
        actions={
          <>
            <button
              type="button"
              onClick={loadContext}
              className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${loadingContext ? 'animate-spin' : ''}`} />
              Sync Data
            </button>
            <button
              type="button"
              disabled={comparing || running}
              onClick={handleCompareModels}
              className="inline-flex items-center gap-1.5 rounded-lg border border-teal-300 bg-teal-50 px-3.5 py-2 text-xs font-semibold text-teal-800 hover:bg-teal-100 disabled:opacity-50"
            >
              <GitCompare className="h-3.5 w-3.5" />
              {comparing ? 'Comparing...' : 'Compare Both Models'}
            </button>
            <button
              type="button"
              disabled={running || comparing}
              onClick={handleRunOptimization}
              className="inline-flex items-center gap-1.5 rounded-lg bg-teal-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-teal-700 disabled:opacity-50"
            >
              <Play className="h-3.5 w-3.5" />
              {running ? 'Solving LP...' : 'Run Optimization'}
            </button>
          </>
        }
      />

      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-xs text-red-800">
          <strong>Error:</strong> {error}
        </div>
      )}

      {/* A. Optimization Configuration Card */}
      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-3.5">
          <div className="flex items-center gap-2">
            <Cpu className="h-4 w-4 text-teal-600" />
            <h2 className="text-sm font-bold text-slate-900">
              Optimization Configuration &amp; Network Scope
            </h2>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-xs text-slate-600">
            <span className="rounded-full bg-slate-100 px-2.5 py-0.5 font-medium">
              {warehouses.length} Active Warehouses
            </span>
            <span className="rounded-full bg-slate-100 px-2.5 py-0.5 font-medium">
              {hospitals.length} Active Hospitals
            </span>
            <span className="rounded-full bg-slate-100 px-2.5 py-0.5 font-medium">
              {products.length} Products
            </span>
            <span className="rounded-full bg-teal-50 px-2.5 py-0.5 font-semibold text-teal-800">
              {openDemandCount} Actionable Demands ({formatNumber(openDemandUnits)} units total
              {selectedScopeDemandUnits !== openDemandUnits
                ? ` · ${formatNumber(selectedScopeDemandUnits)} in current selection`
                : ''}
              )
            </span>
          </div>
        </div>

        <div className="mt-4 grid grid-cols-1 gap-5 lg:grid-cols-3">
          {/* Method Selection */}
          <div>
            <p className="text-xs font-semibold text-slate-700">Optimization Method</p>
            <div className="mt-2 space-y-2">
              <label
                className={`flex cursor-pointer items-start gap-2.5 rounded-lg border p-3 text-xs transition ${
                  method === 'lexicographic_priority'
                    ? 'border-teal-600 bg-teal-50/50'
                    : 'border-slate-200 hover:bg-slate-50'
                }`}
              >
                <input
                  type="radio"
                  name="optMethod"
                  checked={method === 'lexicographic_priority'}
                  onChange={() => setMethod('lexicographic_priority')}
                  className="mt-0.5 text-teal-600 focus:ring-teal-600"
                />
                <div>
                  <p className="font-semibold text-slate-900">
                    Lexicographic Priority Optimization
                  </p>
                  <p className="mt-0.5 text-[11px] text-slate-500">
                    4-stage sequential LP: Critical &rarr; High &rarr; Normal &rarr; Transport Cost.
                  </p>
                </div>
              </label>

              <label
                className={`flex cursor-pointer items-start gap-2.5 rounded-lg border p-3 text-xs transition ${
                  method === 'transportation_lp'
                    ? 'border-teal-600 bg-teal-50/50'
                    : 'border-slate-200 hover:bg-slate-50'
                }`}
              >
                <input
                  type="radio"
                  name="optMethod"
                  checked={method === 'transportation_lp'}
                  onChange={() => setMethod('transportation_lp')}
                  className="mt-0.5 text-teal-600 focus:ring-teal-600"
                />
                <div>
                  <p className="font-semibold text-slate-900">
                    Multi-Commodity Transportation LP
                  </p>
                  <p className="mt-0.5 text-[11px] text-slate-500">
                    Priority-neutral minimum-cost distribution maximizing total volume.
                  </p>
                </div>
              </label>
            </div>

            <div className="mt-3 space-y-1.5 text-xs text-slate-700">
              <label className="flex cursor-pointer items-center gap-2">
                <input
                  type="checkbox"
                  checked={enforceRouteAvailability}
                  onChange={(e) => setEnforceRouteAvailability(e.target.checked)}
                  className="rounded border-slate-300 text-teal-600 focus:ring-teal-600"
                />
                Enforce road corridor availability (A_ij)
              </label>
              {method === 'transportation_lp' && (
                <label className="flex cursor-pointer items-center gap-2">
                  <input
                    type="checkbox"
                    checked={allowUnmetDemand}
                    onChange={(e) => setAllowUnmetDemand(e.target.checked)}
                    className="rounded border-slate-300 text-teal-600 focus:ring-teal-600"
                  />
                  Allow unmet-demand slack (u_jk &ge; 0)
                </label>
              )}
            </div>
          </div>

          {/* Warehouse & Product Filter Chips */}
          <div className="space-y-4">
            <div>
              <div className="flex items-center justify-between text-xs">
                <span className="font-semibold text-slate-700">
                  Warehouses ({selectedWarehouses.length}/{warehouses.length})
                </span>
                <button
                  type="button"
                  onClick={() => setSelectedWarehouses(warehouses.map((w) => w.code))}
                  className="text-[11px] font-semibold text-teal-700 hover:underline"
                >
                  Select All
                </button>
              </div>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {warehouses.map((wh) => {
                  const active = selectedWarehouses.includes(wh.code);
                  return (
                    <button
                      key={wh.code}
                      type="button"
                      onClick={() =>
                        toggleSelection(wh.code, selectedWarehouses, setSelectedWarehouses)
                      }
                      className={`rounded-md border px-2.5 py-1 text-xs font-medium transition ${
                        active
                          ? 'border-teal-600 bg-teal-600 text-white'
                          : 'border-slate-200 bg-slate-50 text-slate-600 hover:bg-slate-100'
                      }`}
                    >
                      {wh.code} ({wh.area})
                    </button>
                  );
                })}
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between text-xs">
                <span className="font-semibold text-slate-700">
                  Medical Products ({selectedProducts.length}/{products.length})
                </span>
                <button
                  type="button"
                  onClick={() => setSelectedProducts(products.map((p) => p.code))}
                  className="text-[11px] font-semibold text-teal-700 hover:underline"
                >
                  Select All
                </button>
              </div>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {products.map((prod) => {
                  const active = selectedProducts.includes(prod.code);
                  return (
                    <button
                      key={prod.code}
                      type="button"
                      onClick={() =>
                        toggleSelection(prod.code, selectedProducts, setSelectedProducts)
                      }
                      className={`rounded-md border px-2.5 py-1 text-xs font-medium transition ${
                        active
                          ? 'border-navy-800 bg-navy-900 text-white'
                          : 'border-slate-200 bg-slate-50 text-slate-600 hover:bg-slate-100'
                      }`}
                    >
                      {prod.name}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Hospital Filter Chips */}
          <div>
            <div className="flex items-center justify-between text-xs">
              <span className="font-semibold text-slate-700">
                Hospitals ({selectedHospitals.length}/{hospitals.length})
              </span>
              <button
                type="button"
                onClick={() => setSelectedHospitals(hospitals.map((h) => h.code))}
                className="text-[11px] font-semibold text-teal-700 hover:underline"
              >
                Select All
              </button>
            </div>
            <div className="mt-2 flex max-h-40 flex-wrap gap-1.5 overflow-y-auto pr-1">
              {hospitals.map((hosp) => {
                const active = selectedHospitals.includes(hosp.code);
                const dotColor =
                  hosp.priority_level === 'critical'
                    ? 'bg-red-500'
                    : hosp.priority_level === 'high'
                    ? 'bg-orange-400'
                    : 'bg-emerald-500';
                return (
                  <button
                    key={hosp.code}
                    type="button"
                    onClick={() =>
                      toggleSelection(hosp.code, selectedHospitals, setSelectedHospitals)
                    }
                    className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-xs font-medium transition ${
                      active
                        ? 'border-teal-600 bg-teal-50 text-teal-900'
                        : 'border-slate-200 bg-slate-50 text-slate-500 hover:bg-slate-100'
                    }`}
                  >
                    <span className={`h-2 w-2 rounded-full ${dotColor}`} />
                    <span>{hosp.code}</span>
                    <span className="text-[10px] opacity-75">{hosp.area}</span>
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      {/* B. Optimization Summary Strip */}
      {activeResult && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2.5">
              <span className="rounded-md bg-navy-900 px-2.5 py-1 text-xs font-bold text-white">
                {activeResult.run_code}
              </span>
              <StatusBadge status={activeResult.solver_status} />
              <span className="rounded-full bg-teal-50 px-2.5 py-0.5 text-[11px] font-semibold text-teal-800">
                Planned Allocation Only
              </span>
            </div>
            <span className="text-xs text-slate-500">
              Model:{' '}
              <strong>
                {activeResult.model_type === 'lexicographic_priority'
                  ? '4-Stage Lexicographic Priority'
                  : 'Multi-Commodity Transportation LP'}
              </strong>{' '}
              &bull; Solved in <strong>{activeResult.execution_time_ms} ms</strong>
            </span>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard
              title="Demand Included in Run"
              value={`${formatNumber(activeResult.total_demand)} units`}
              subtitle={
                activeResult.formulation_summary?.sets
                  ? `${activeResult.formulation_summary.sets.hospitals_count} hospitals · ${activeResult.formulation_summary.sets.warehouses_count} warehouses · ${activeResult.formulation_summary.sets.products_count} products`
                  : 'Immutable snapshot for this run'
              }
              icon={Activity}
              accent="slate"
              sourceTag="Run Snapshot"
            />
            <StatCard
              title="Allocated Quantity"
              value={`${formatNumber(activeResult.total_allocated)} units`}
              subtitle={`${formatPercent(activeResult.fulfillment_percentage)} fulfillment for run`}
              icon={CheckCircle2}
              accent="emerald"
              sourceTag={activeResult.solver_status}
            />
            <StatCard
              title="Unmet Demand in Run"
              value={`${formatNumber(activeResult.total_unmet_demand)} units`}
              subtitle="Residual shortage in this run"
              icon={AlertTriangle}
              accent={activeResult.total_unmet_demand > 0 ? 'red' : 'emerald'}
              sourceTag="u[j,k]"
            />
            <StatCard
              title="Total Transport Cost"
              value={formatCurrencyINR(activeResult.total_cost)}
              subtitle={`${activeResult.execution_time_ms} ms (${activeResult.allocations.length} routes)`}
              icon={IndianRupee}
              accent="teal"
              sourceTag="PuLP CBC"
            />
          </div>
        </div>
      )}

      {/* Navigation Tabs */}
      <div className="border-b border-slate-200">
        <nav className="-mb-px flex flex-wrap gap-1">
          {TABS.map(({ id, label, icon: Icon }) => {
            const active = activeTab === id;
            return (
              <button
                key={id}
                type="button"
                onClick={() => setActiveTab(id)}
                className={`inline-flex items-center gap-1.5 border-b-2 px-4 py-2.5 text-xs font-semibold transition ${
                  active
                    ? 'border-teal-600 text-teal-700'
                    : 'border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-800'
                }`}
              >
                <Icon className="h-3.5 w-3.5" />
                <span>{label}</span>
                {id === 'history' && (
                  <span className="rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-600">
                    {runs.length}
                  </span>
                )}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Tab Content */}
      {activeTab === 'history' ? (
        <DataTable
          columns={historyColumns}
          rows={runs}
          loading={loadingContext}
          emptyMessage="No historical optimization runs recorded yet. Click 'Run Optimization' above."
        />
      ) : activeTab === 'compare' ? (
        <ModelComparisonPanel
          comparison={comparison}
          onRunCompare={handleCompareModels}
          loading={comparing}
        />
      ) : !activeResult ? (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white p-10 text-center">
          <TrendingUp className="mx-auto h-8 w-8 text-teal-600" />
          <h3 className="mt-3 text-sm font-bold text-slate-900">
            Ready to Compute Optimal Emergency Supply Allocation
          </h3>
          <p className="mx-auto mt-1.5 max-w-xl text-xs text-slate-600">
            Select your optimization method and click <strong>Run Optimization</strong> to solve
            with PuLP CBC using live warehouse stock, hospital demands, and route corridors.
          </p>
        </div>
      ) : activeTab === 'overview' ? (
        <div className="space-y-6">
          {/* C. Priority-Tier Analysis Cards */}
          <div>
            <h3 className="mb-3 text-sm font-bold text-slate-900">
              Priority-Tier Fulfillment &amp; Shortage Analysis
            </h3>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
              {(activeResult.priority_summary || []).map((tier) => {
                const borderStyle =
                  tier.priority_level === 'critical'
                    ? 'border-red-200 bg-red-50/40'
                    : tier.priority_level === 'high'
                    ? 'border-orange-200 bg-orange-50/40'
                    : 'border-emerald-200 bg-emerald-50/40';
                const barColor =
                  tier.priority_level === 'critical'
                    ? 'bg-red-600'
                    : tier.priority_level === 'high'
                    ? 'bg-orange-500'
                    : 'bg-emerald-600';
                return (
                  <div
                    key={tier.priority_level}
                    className={`rounded-xl border p-5 shadow-sm ${borderStyle}`}
                  >
                    <div className="flex items-center justify-between">
                      <StatusBadge status={tier.priority_level} />
                      <span className="text-xs text-slate-500">
                        {tier.hospital_count} hospital(s)
                      </span>
                    </div>
                    <p className="mt-3 text-2xl font-bold text-slate-900">
                      {formatPercent(tier.fulfillment_pct)}
                    </p>
                    <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-white/80">
                      <div
                        className={`h-full rounded-full ${barColor}`}
                        style={{ width: `${Math.min(100, tier.fulfillment_pct)}%` }}
                      />
                    </div>
                    <div className="mt-3 flex items-center justify-between text-xs text-slate-700">
                      <span>
                        Allocated: <strong>{formatNumber(tier.total_allocated)}</strong> /{' '}
                        {formatNumber(tier.total_demand)}
                      </span>
                      <span className={tier.total_unmet > 0 ? 'font-bold text-red-700' : 'text-emerald-700'}>
                        Unmet: {formatNumber(tier.total_unmet)}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Hospital-Wise Allocations Summary */}
          <div>
            <h3 className="mb-3 text-sm font-bold text-slate-900">
              Hospital-Wise Planned Allocation Summary
            </h3>
            <DataTable
              columns={hospitalSummaryColumns}
              rows={activeResult.hospital_summary || []}
              defaultSortKey="hospital_code"
              emptyMessage="No hospital allocation summary available."
            />
          </div>
        </div>
      ) : activeTab === 'allocations' ? (
        <div className="space-y-5">
          {/* Allocation Table Filter Bar */}
          <div className="flex flex-col gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm lg:flex-row lg:items-center lg:justify-between">
            <div className="relative flex-1 max-w-md">
              <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
              <input
                type="text"
                value={allocSearch}
                onChange={(e) => setAllocSearch(e.target.value)}
                placeholder="Filter allocations by warehouse, hospital, product, or route..."
                className="w-full rounded-lg border border-slate-300 py-2 pl-9 pr-3 text-xs text-slate-900 focus:border-teal-600 focus:outline-none"
              />
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <select
                value={allocWhFilter}
                onChange={(e) => setAllocWhFilter(e.target.value)}
                className="rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-700"
              >
                <option value="all">All Warehouses</option>
                {warehouses.map((w) => (
                  <option key={w.code} value={w.code}>
                    {w.code}
                  </option>
                ))}
              </select>
              <select
                value={allocProdFilter}
                onChange={(e) => setAllocProdFilter(e.target.value)}
                className="rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-700"
              >
                <option value="all">All Products</option>
                {products.map((p) => (
                  <option key={p.code} value={p.code}>
                    {p.name}
                  </option>
                ))}
              </select>
              <select
                value={allocPrioFilter}
                onChange={(e) => setAllocPrioFilter(e.target.value)}
                className="rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-700"
              >
                <option value="all">All Priorities</option>
                <option value="critical">Critical</option>
                <option value="high">High</option>
                <option value="normal">Normal</option>
              </select>
              <span className="text-xs text-slate-500">
                {filteredAllocations.length} allocation(s)
              </span>
            </div>
          </div>

          <DataTable
            columns={allocationColumns}
            rows={filteredAllocations}
            defaultSortKey="warehouse_code"
            emptyMessage="No non-zero planned allocations match the current filters."
          />

          {/* Unmet Shortages Table */}
          {(activeResult.unmet_demands || []).some((u) => u.unmet_quantity > 0) && (
            <div>
              <h3 className="mb-3 text-sm font-bold text-red-700">
                Unmet Demand Breakdown (u[j,k] &gt; 0)
              </h3>
              <DataTable
                columns={[
                  { key: 'hospital_code', header: 'Hospital', sortable: true },
                  {
                    key: 'priority_level',
                    header: 'Priority',
                    sortable: true,
                    render: (r) => <StatusBadge status={r.priority_level} />,
                  },
                  {
                    key: 'product_name',
                    header: 'Product',
                    sortable: true,
                    render: (r) => r.product_name || r.product_code,
                  },
                  {
                    key: 'quantity_requested',
                    header: 'Requested',
                    sortable: true,
                    render: (r) => formatNumber(r.quantity_requested),
                  },
                  {
                    key: 'quantity_allocated',
                    header: 'Allocated',
                    sortable: true,
                    render: (r) => formatNumber(r.quantity_allocated),
                  },
                  {
                    key: 'unmet_quantity',
                    header: 'Unmet Shortage',
                    sortable: true,
                    render: (r) => (
                      <span className="font-bold text-red-600">
                        {formatNumber(r.unmet_quantity)}
                      </span>
                    ),
                  },
                ]}
                rows={(activeResult.unmet_demands || []).filter((u) => u.unmet_quantity > 0)}
                defaultSortKey="unmet_quantity"
                defaultSortDir="desc"
              />
            </div>
          )}
        </div>
      ) : activeTab === 'charts' ? (
        <OptimizationCharts result={activeResult} />
      ) : (
        <MathematicalExplanationPanel result={activeResult} />
      )}
    </div>
  );
}
