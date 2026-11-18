import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  ClipboardList,
  Clock,
  Pencil,
  Plus,
  RefreshCw,
  Search,
  Trash2,
} from 'lucide-react';
import PageHeader from '../components/common/PageHeader';
import StatCard from '../components/common/StatCard';
import DataTable from '../components/tables/DataTable';
import StatusBadge from '../components/common/StatusBadge';
import Modal from '../components/common/Modal';
import ConfirmDialog from '../components/common/ConfirmDialog';
import { useToast } from '../components/common/ToastContext';
import {
  FormErrorBanner,
  SelectInput,
  TextInput,
} from '../components/forms/FormFields';
import { demandService } from '../services/demandService';
import { hospitalService } from '../services/hospitalService';
import { inventoryService } from '../services/inventoryService';
import { optimizationService } from '../services/optimizationService';
import {
  extractApiError,
  formatNumber,
  generateNextCode,
} from '../utils/formatters';

const PRIORITY_OPTIONS = [
  { value: 'critical', label: 'Critical (Tier 1)' },
  { value: 'high', label: 'High (Tier 2)' },
  { value: 'normal', label: 'Normal (Tier 3)' },
];

const STATUS_OPTIONS = [
  { value: 'open', label: 'Open' },
  { value: 'partially_fulfilled', label: 'Partially Fulfilled' },
  { value: 'fulfilled', label: 'Fulfilled' },
  { value: 'cancelled', label: 'Cancelled' },
];

const PRIORITY_RANK = { critical: 1, high: 2, normal: 3 };

const INITIAL_FORM = {
  demand_code: '',
  hospital_id: '',
  product_id: '',
  quantity_requested: '50',
  priority_level: 'normal',
  status: 'open',
  data_note: 'Manual demand request',
};

function validateDemandForm(form, isEdit) {
  const errors = {};
  if (!isEdit) {
    if (!form.demand_code.trim() || form.demand_code.trim().length < 2) {
      errors.demand_code = 'Demand code must be at least 2 characters (e.g., DEM-033).';
    }
    if (!form.hospital_id) {
      errors.hospital_id = 'Please select a hospital.';
    }
    if (!form.product_id) {
      errors.product_id = 'Please select a medical product.';
    }
  }

  const qty = Number(form.quantity_requested);
  if (
    form.quantity_requested === '' ||
    Number.isNaN(qty) ||
    !Number.isInteger(qty) ||
    qty <= 0
  ) {
    errors.quantity_requested = 'Requested quantity must be a positive whole number (> 0).';
  }

  return errors;
}

export default function Demands() {
  const toast = useToast();
  const [demands, setDemands] = useState([]);
  const [hospitals, setHospitals] = useState([]);
  const [products, setProducts] = useState([]);
  const [latestRunInfo, setLatestRunInfo] = useState({
    run_code: null,
    model_type: null,
    allocations_by_pair: {},
  });
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);

  // Filters
  const [search, setSearch] = useState('');
  const [hospitalFilter, setHospitalFilter] = useState('all');
  const [productFilter, setProductFilter] = useState('all');
  const [priorityFilter, setPriorityFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');

  // Create / Edit modal state
  const [formOpen, setFormOpen] = useState(false);
  const [editingDemand, setEditingDemand] = useState(null);
  const [form, setForm] = useState(INITIAL_FORM);
  const [fieldErrors, setFieldErrors] = useState({});
  const [submitError, setSubmitError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  // Inline status update tracking
  const [updatingStatusId, setUpdatingStatusId] = useState(null);

  // Delete confirmation
  const [deletingDemand, setDeletingDemand] = useState(null);
  const [deleting, setDeleting] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const [demRows, hospRows, prodRows, latestAllocs] = await Promise.all([
        demandService.list(),
        hospitalService.list(),
        inventoryService.listProducts(),
        optimizationService
          .getLatestAllocations()
          .catch(() => ({ run_code: null, model_type: null, allocations_by_pair: {} })),
      ]);
      setDemands(demRows);
      setHospitals(hospRows);
      setProducts(prodRows);
      setLatestRunInfo(latestAllocs);
    } catch (err) {
      setLoadError(
        extractApiError(err, 'Unable to load hospital demand requests from backend API.')
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const hospitalById = useMemo(
    () => Object.fromEntries(hospitals.map((h) => [h.id, h])),
    [hospitals]
  );

  const productById = useMemo(
    () => Object.fromEntries(products.map((p) => [p.id, p])),
    [products]
  );

  const enrichedDemands = useMemo(() => {
    const hasSolverRun = Boolean(latestRunInfo?.run_code);
    const allocMap = latestRunInfo?.allocations_by_pair || {};

    return demands.map((d) => {
      const hospital = hospitalById[d.hospital_id];
      const product = productById[d.product_id];
      const req = Number(d.quantity_requested || 0);
      const pairKey = `${d.hospital_id}:${d.product_id}`;

      let fulfilledQty = null;
      let pendingQty = 0;
      let unmetQty = null;

      if (d.status === 'fulfilled') {
        fulfilledQty = req;
        pendingQty = 0;
        unmetQty = 0;
      } else if (d.status === 'cancelled') {
        fulfilledQty = 0;
        pendingQty = 0;
        unmetQty = 0;
      } else {
        // open or partially_fulfilled
        if (hasSolverRun) {
          const solvedAlloc = Math.min(req, Number(allocMap[pairKey] || 0));
          fulfilledQty = solvedAlloc;
          unmetQty = Math.max(0, req - solvedAlloc);
          pendingQty = d.status === 'open' ? req : unmetQty;
        } else {
          fulfilledQty = null;
          pendingQty = req;
          unmetQty = null;
        }
      }

      return {
        ...d,
        hospitalCode: hospital?.code || `HOSP-#${d.hospital_id}`,
        hospitalName: hospital?.name || `Hospital #${d.hospital_id}`,
        hospitalArea: hospital?.area || '',
        productCode: product?.code || `PROD-#${d.product_id}`,
        productName: product?.name || `Product #${d.product_id}`,
        productUnit: product?.unit || 'units',
        fulfilledQty,
        pendingQty,
        unmetQty,
      };
    });
  }, [demands, hospitalById, productById, latestRunInfo]);

  const filteredDemands = useMemo(() => {
    const q = search.trim().toLowerCase();
    return enrichedDemands.filter((d) => {
      if (hospitalFilter !== 'all' && String(d.hospital_id) !== hospitalFilter) return false;
      if (productFilter !== 'all' && String(d.product_id) !== productFilter) return false;
      if (priorityFilter !== 'all' && d.priority_level !== priorityFilter) return false;
      if (statusFilter !== 'all' && d.status !== statusFilter) return false;
      if (!q) return true;
      return (
        d.demand_code.toLowerCase().includes(q) ||
        d.hospitalCode.toLowerCase().includes(q) ||
        d.hospitalName.toLowerCase().includes(q) ||
        d.productCode.toLowerCase().includes(q) ||
        d.productName.toLowerCase().includes(q)
      );
    });
  }, [
    enrichedDemands,
    search,
    hospitalFilter,
    productFilter,
    priorityFilter,
    statusFilter,
  ]);

  const summary = useMemo(() => {
    const openCount = demands.filter((d) => d.status === 'open').length;
    const criticalOpen = demands.filter(
      (d) => d.status === 'open' && d.priority_level === 'critical'
    ).length;
    const totalPendingQty = enrichedDemands.reduce((s, d) => s + Number(d.pendingQty || 0), 0);
    const totalFulfilledQty = enrichedDemands.reduce(
      (s, d) => s + Number(d.fulfilledQty || 0),
      0
    );
    const totalUnmetQty = enrichedDemands.reduce((s, d) => s + Number(d.unmetQty || 0), 0);
    return {
      openCount,
      criticalOpen,
      totalPendingQty,
      totalFulfilledQty,
      totalUnmetQty,
    };
  }, [demands, enrichedDemands]);

  function openCreateModal() {
    const firstHospital = hospitals[0];
    setEditingDemand(null);
    setForm({
      ...INITIAL_FORM,
      demand_code: generateNextCode(
        'DEM',
        demands.map((d) => d.demand_code),
        3
      ),
      hospital_id: firstHospital ? String(firstHospital.id) : '',
      product_id: products[0] ? String(products[0].id) : '',
      priority_level: firstHospital?.priority_level || 'normal',
    });
    setFieldErrors({});
    setSubmitError(null);
    setFormOpen(true);
  }

  function openEditModal(demand) {
    setEditingDemand(demand);
    setForm({
      demand_code: demand.demand_code,
      hospital_id: String(demand.hospital_id),
      product_id: String(demand.product_id),
      quantity_requested: String(demand.quantity_requested),
      priority_level: demand.priority_level,
      status: demand.status,
      data_note: demand.data_note || '',
    });
    setFieldErrors({});
    setSubmitError(null);
    setFormOpen(true);
  }

  function handleFieldChange(e) {
    const { name, value } = e.target;
    setForm((prev) => {
      const next = { ...prev, [name]: value };
      // Follow existing business logic: default demand priority to selected hospital's priority
      if (name === 'hospital_id' && !editingDemand) {
        const selectedHospital = hospitalById[Number(value)];
        if (selectedHospital?.priority_level) {
          next.priority_level = selectedHospital.priority_level;
        }
      }
      return next;
    });
    if (fieldErrors[name]) {
      setFieldErrors((prev) => ({ ...prev, [name]: undefined }));
    }
  }

  async function handleFormSubmit(e) {
    e.preventDefault();
    const isEdit = Boolean(editingDemand);
    const errors = validateDemandForm(form, isEdit);
    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors);
      return;
    }

    setSubmitting(true);
    setSubmitError(null);
    try {
      if (isEdit) {
        await demandService.update(editingDemand.id, {
          quantity_requested: Number(form.quantity_requested),
          priority_level: form.priority_level,
          status: form.status,
          data_note: form.data_note.trim() || null,
        });
        toast.success(
          'Demand updated',
          `${editingDemand.demand_code} updated successfully.`
        );
      } else {
        await demandService.create({
          demand_code: form.demand_code.trim().toUpperCase(),
          hospital_id: Number(form.hospital_id),
          product_id: Number(form.product_id),
          quantity_requested: Number(form.quantity_requested),
          priority_level: form.priority_level,
          status: form.status,
          data_note: form.data_note.trim() || null,
        });
        toast.success(
          'Demand request created',
          `${form.demand_code.trim().toUpperCase()} added to open demand queue.`
        );
      }
      setFormOpen(false);
      await loadData();
    } catch (err) {
      const msg = extractApiError(err, 'Failed to save demand request.');
      setSubmitError(msg);
      toast.error('Save failed', msg);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleQuickStatusChange(demand, newStatus) {
    if (demand.status === newStatus) return;
    setUpdatingStatusId(demand.id);
    try {
      const updated = await demandService.update(demand.id, { status: newStatus });
      setDemands((prev) => prev.map((d) => (d.id === demand.id ? updated : d)));
      toast.success(
        'Status updated',
        `${demand.demand_code} marked as ${newStatus.replace(/_/g, ' ')}.`
      );
    } catch (err) {
      toast.error(
        'Status update failed',
        extractApiError(err, 'Could not update demand status.')
      );
    } finally {
      setUpdatingStatusId(null);
    }
  }

  async function handleConfirmDelete() {
    if (!deletingDemand) return;
    setDeleting(true);
    try {
      await demandService.remove(deletingDemand.id);
      toast.success(
        'Demand deleted',
        `${deletingDemand.demand_code} removed from the system.`
      );
      setDeletingDemand(null);
      await loadData();
    } catch (err) {
      toast.error(
        'Delete failed',
        extractApiError(err, 'Could not delete demand request.')
      );
      setDeletingDemand(null);
    } finally {
      setDeleting(false);
    }
  }

  const columns = [
    {
      key: 'demand_code',
      header: 'Code',
      sortable: true,
      render: (r) => <span className="font-semibold text-slate-900">{r.demand_code}</span>,
    },
    {
      key: 'hospitalCode',
      header: 'Hospital',
      sortable: true,
      render: (r) => (
        <div>
          <span className="font-semibold text-slate-800">{r.hospitalCode}</span>
          <span className="ml-1.5 text-xs text-slate-500">{r.hospitalArea}</span>
        </div>
      ),
    },
    {
      key: 'productName',
      header: 'Medical Product',
      sortable: true,
      render: (r) => (
        <div>
          <span className="font-medium text-slate-900">{r.productName}</span>
          <span className="ml-1 text-xs text-slate-400">({r.productCode})</span>
        </div>
      ),
    },
    {
      key: 'quantity_requested',
      header: 'Requested',
      sortable: true,
      render: (r) => (
        <span className="font-bold text-slate-900">
          {formatNumber(r.quantity_requested)}{' '}
          <span className="text-xs font-normal text-slate-500">{r.productUnit}</span>
        </span>
      ),
    },
    {
      key: 'fulfillment',
      header: 'Fulfilled / Pending / Unmet',
      render: (r) => (
        <div className="flex items-center gap-2 text-xs">
          <span className="text-emerald-700 font-semibold" title="Fulfilled / Latest Solved Allocation">
            {r.fulfilledQty === null ? '—' : formatNumber(r.fulfilledQty)}
          </span>
          <span className="text-slate-300">/</span>
          <span className="text-teal-700 font-semibold" title="Pending Quantity">
            {formatNumber(r.pendingQty)}
          </span>
          <span className="text-slate-300">/</span>
          <span
            className={`font-semibold ${
              r.unmetQty && r.unmetQty > 0 ? 'text-red-600' : 'text-slate-500'
            }`}
            title="Unmet Shortage Quantity"
          >
            {r.unmetQty === null ? '—' : formatNumber(r.unmetQty)}
          </span>
        </div>
      ),
    },
    {
      key: 'priority_level',
      header: 'Priority',
      sortable: true,
      sortValue: (r) => PRIORITY_RANK[r.priority_level] || 99,
      render: (r) => <StatusBadge status={r.priority_level} />,
    },
    {
      key: 'status',
      header: 'Status',
      sortable: true,
      render: (r) => (
        <div className="flex items-center gap-2">
          <StatusBadge status={r.status} />
          <select
            aria-label={`Change status for ${r.demand_code}`}
            value={r.status}
            disabled={updatingStatusId === r.id}
            onChange={(e) => handleQuickStatusChange(r, e.target.value)}
            className="rounded-md border border-slate-200 bg-white px-2 py-1 text-[11px] font-medium text-slate-700 hover:border-slate-300 focus:border-teal-600 focus:outline-none disabled:opacity-50"
          >
            {STATUS_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
      ),
    },
    {
      key: 'actions',
      header: 'Actions',
      render: (r) => (
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={() => openEditModal(r)}
            title="Edit demand request"
            className="rounded-lg border border-slate-200 p-1.5 text-slate-600 transition hover:border-teal-200 hover:bg-teal-50 hover:text-teal-700"
          >
            <Pencil className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            onClick={() => setDeletingDemand(r)}
            title="Delete demand request"
            className="rounded-lg border border-slate-200 p-1.5 text-slate-600 transition hover:border-red-200 hover:bg-red-50 hover:text-red-600"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        </div>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="Hospital Demand Requests"
        badge="Synthetic Demand"
        description="Create, prioritize, track, and update emergency medical supply requests across Pune and Pimpri-Chinchwad hospitals."
        actions={
          <>
            <button
              type="button"
              onClick={loadData}
              className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </button>
            <button
              type="button"
              onClick={openCreateModal}
              className="inline-flex items-center gap-1.5 rounded-lg bg-teal-600 px-4 py-2 text-xs font-semibold text-white shadow-sm transition hover:bg-teal-700"
            >
              <Plus className="h-4 w-4" />
              New Demand Request
            </button>
          </>
        }
      />

      {loadError && (
        <div className="mb-5 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-xs text-red-800">
          {loadError}
        </div>
      )}

      {/* KPI Strip */}
      <div className="mb-5 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Open Requests"
          value={formatNumber(summary.openCount)}
          subtitle={`Out of ${demands.length} total requests`}
          icon={ClipboardList}
          accent="teal"
        />
        <StatCard
          title="Critical Open Demands"
          value={formatNumber(summary.criticalOpen)}
          subtitle="Tier-1 emergency priority"
          icon={AlertTriangle}
          accent="red"
        />
        <StatCard
          title="Pending Units"
          value={`${formatNumber(summary.totalPendingQty)} units`}
          subtitle="Awaiting fulfillment"
          icon={Clock}
          accent="orange"
        />
        <StatCard
          title="Fulfilled / Unmet (Latest Run)"
          value={
            latestRunInfo.run_code
              ? `${formatNumber(summary.totalFulfilledQty)} / ${formatNumber(summary.totalUnmetQty)}`
              : 'Not solved yet'
          }
          subtitle={
            latestRunInfo.run_code
              ? `From ${latestRunInfo.run_code}`
              : 'Run Optimization to compute'
          }
          icon={CheckCircle2}
          accent="emerald"
          sourceTag={latestRunInfo.run_code ? 'Latest Solver Run' : 'Pending Run'}
        />
      </div>

      {/* Filter Toolbar */}
      <div className="mb-4 flex flex-col gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
          <div className="relative flex-1 max-w-md">
            <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by demand code, hospital, or product..."
              className="w-full rounded-lg border border-slate-300 py-2 pl-9 pr-3 text-xs text-slate-900 focus:border-teal-600 focus:outline-none focus:ring-2 focus:ring-teal-600/20"
            />
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <select
              value={hospitalFilter}
              onChange={(e) => setHospitalFilter(e.target.value)}
              className="rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-700 focus:border-teal-600 focus:outline-none"
            >
              <option value="all">All Hospitals</option>
              {hospitals.map((h) => (
                <option key={h.id} value={String(h.id)}>
                  {h.code} — {h.area}
                </option>
              ))}
            </select>

            <select
              value={productFilter}
              onChange={(e) => setProductFilter(e.target.value)}
              className="rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-700 focus:border-teal-600 focus:outline-none"
            >
              <option value="all">All Products</option>
              {products.map((p) => (
                <option key={p.id} value={String(p.id)}>
                  {p.code} — {p.name}
                </option>
              ))}
            </select>

            <select
              value={priorityFilter}
              onChange={(e) => setPriorityFilter(e.target.value)}
              className="rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-700 focus:border-teal-600 focus:outline-none"
            >
              <option value="all">All Priorities</option>
              <option value="critical">Critical</option>
              <option value="high">High</option>
              <option value="normal">Normal</option>
            </select>

            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-700 focus:border-teal-600 focus:outline-none"
            >
              <option value="all">All Statuses</option>
              {STATUS_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 pt-2.5 text-[11px] text-slate-500">
          <span>
            Showing <strong>{filteredDemands.length}</strong> of {demands.length} demand
            request(s)
          </span>
          <span>
            {latestRunInfo.run_code
              ? `Fulfilled / Unmet columns reflect latest persisted solver run (${latestRunInfo.run_code}).`
              : 'Fulfilled / Unmet columns populate automatically after running the OR Optimizer.'}
          </span>
        </div>
      </div>

      <DataTable
        columns={columns}
        rows={filteredDemands}
        loading={loading}
        defaultSortKey="demand_code"
        emptyMessage="No demand requests match the selected filters."
      />

      {/* Create / Edit Demand Modal */}
      <Modal
        open={formOpen}
        onClose={submitting ? undefined : () => setFormOpen(false)}
        title={
          editingDemand
            ? `Edit Demand Request — ${editingDemand.demand_code}`
            : 'Create Hospital Demand Request'
        }
        subtitle="Priority defaults to the hospital's current emergency tier and can be adjusted if needed."
        footer={
          <>
            <button
              type="button"
              disabled={submitting}
              onClick={() => setFormOpen(false)}
              className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              form="demand-form"
              disabled={submitting}
              className="rounded-lg bg-teal-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-teal-700 disabled:opacity-50"
            >
              {submitting
                ? 'Saving...'
                : editingDemand
                ? 'Save Changes'
                : 'Create Demand Request'}
            </button>
          </>
        }
      >
        <form id="demand-form" onSubmit={handleFormSubmit} className="space-y-4">
          <FormErrorBanner message={submitError} />

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <TextInput
              label="Demand Code"
              name="demand_code"
              value={form.demand_code}
              onChange={handleFieldChange}
              placeholder="DEM-033"
              required
              disabled={Boolean(editingDemand)}
              error={fieldErrors.demand_code}
            />
            <TextInput
              label="Requested Quantity"
              name="quantity_requested"
              type="number"
              min="1"
              step="1"
              value={form.quantity_requested}
              onChange={handleFieldChange}
              required
              error={fieldErrors.quantity_requested}
              hint="Must be a positive integer."
            />
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <SelectInput
              label="Hospital"
              name="hospital_id"
              value={form.hospital_id}
              onChange={handleFieldChange}
              placeholder="Select hospital"
              required
              disabled={Boolean(editingDemand)}
              error={fieldErrors.hospital_id}
              options={hospitals.map((h) => ({
                value: String(h.id),
                label: `${h.code} — ${h.area} (${h.priority_level})`,
              }))}
            />
            <SelectInput
              label="Medical Product"
              name="product_id"
              value={form.product_id}
              onChange={handleFieldChange}
              placeholder="Select product"
              required
              disabled={Boolean(editingDemand)}
              error={fieldErrors.product_id}
              options={products.map((p) => ({
                value: String(p.id),
                label: `${p.code} — ${p.name} (${p.unit})`,
              }))}
            />
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <SelectInput
              label="Emergency Priority"
              name="priority_level"
              value={form.priority_level}
              onChange={handleFieldChange}
              options={PRIORITY_OPTIONS}
              required
              hint="Auto-matched to hospital priority on selection."
            />
            <SelectInput
              label="Request Status"
              name="status"
              value={form.status}
              onChange={handleFieldChange}
              options={STATUS_OPTIONS}
              required
            />
          </div>

          <TextInput
            label="Request Note"
            name="data_note"
            value={form.data_note}
            onChange={handleFieldChange}
            placeholder="Optional clinical or surge context"
          />
        </form>
      </Modal>

      {/* Delete Confirmation Dialog */}
      <ConfirmDialog
        open={Boolean(deletingDemand)}
        onClose={() => setDeletingDemand(null)}
        onConfirm={handleConfirmDelete}
        loading={deleting}
        tone="danger"
        title="Delete Demand Request?"
        confirmLabel="Delete Request"
        message={
          deletingDemand
            ? `Are you sure you want to delete ${deletingDemand.demand_code} (${deletingDemand.hospitalCode} — ${deletingDemand.productName}, ${formatNumber(
                deletingDemand.quantity_requested
              )} units)?`
            : ''
        }
      />
    </div>
  );
}
