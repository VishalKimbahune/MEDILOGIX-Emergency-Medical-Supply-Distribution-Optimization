import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  AlertTriangle,
  CheckCheck,
  CheckCircle2,
  ClipboardList,
  Clock,
  Pencil,
  Plus,
  RefreshCw,
  Search,
  Trash2,
  XCircle,
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
import { approveHospitalOrder, rejectHospitalOrder } from '../services/adminService';
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
  { value: 'pending_approval', label: 'Pending Approval' },
  { value: 'open', label: 'Open (Approved)' },
  { value: 'partially_fulfilled', label: 'Partially Fulfilled' },
  { value: 'fulfilled', label: 'Fulfilled' },
  { value: 'rejected', label: 'Rejected' },
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

  const [searchParams, setSearchParams] = useSearchParams();
  const urlStatus = searchParams.get('status') || 'all';

  // Filters
  const [search, setSearch] = useState('');
  const [hospitalFilter, setHospitalFilter] = useState('all');
  const [productFilter, setProductFilter] = useState('all');
  const [priorityFilter, setPriorityFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState(urlStatus);
  const [actionLoading, setActionLoading] = useState(false);

  // Sync url param if changed externally
  useEffect(() => {
    if (searchParams.get('status')) {
      setStatusFilter(searchParams.get('status'));
    }
  }, [searchParams]);

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

  async function handleApproveOrder(demand) {
    setActionLoading(true);
    try {
      await approveHospitalOrder(demand.id);
      toast.showToast(`Order ${demand.demand_code} approved for LP optimization!`, 'success');
      await loadData();
    } catch (err) {
      toast.showToast(extractApiError(err, 'Failed to approve order'), 'error');
    } finally {
      setActionLoading(false);
    }
  }

  async function handleRejectOrder(demand) {
    const reason = window.prompt(
      `Enter rejection reason for hospital order ${demand.demand_code}:`,
      'Unable to fulfill due to current operational/inventory constraints'
    );
    if (!reason || reason.trim().length < 2) return;
    setActionLoading(true);
    try {
      await rejectHospitalOrder(demand.id, reason.trim());
      toast.showToast(`Order ${demand.demand_code} rejected`, 'info');
      await loadData();
    } catch (err) {
      toast.showToast(extractApiError(err, 'Failed to reject order'), 'error');
    } finally {
      setActionLoading(false);
    }
  }

  async function handleApproveAll(pendingList) {
    if (!pendingList || pendingList.length === 0) return;
    if (!window.confirm(`Approve all ${pendingList.length} pending hospital orders for LP optimization?`)) {
      return;
    }
    setActionLoading(true);
    let approved = 0;
    try {
      for (const ord of pendingList) {
        await approveHospitalOrder(ord.id);
        approved++;
      }
      toast.showToast(`Approved ${approved} hospital orders. They are now eligible for optimization.`, 'success');
      await loadData();
    } catch (err) {
      toast.showToast(extractApiError(err, 'Failed while approving pending orders'), 'error');
      await loadData();
    } finally {
      setActionLoading(false);
    }
  }

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
      } else if (d.status === 'cancelled' || d.status === 'rejected') {
        fulfilledQty = 0;
        pendingQty = 0;
        unmetQty = 0;
      } else if (d.status === 'pending_approval' || d.approval_status === 'pending_approval') {
        fulfilledQty = 0;
        pendingQty = req;
        unmetQty = req;
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
        isPendingApproval: d.status === 'pending_approval' || d.approval_status === 'pending_approval',
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

  const pendingApprovalOrders = useMemo(() => {
    return enrichedDemands.filter((d) => d.isPendingApproval);
  }, [enrichedDemands]);

  const filteredDemands = useMemo(() => {
    const q = search.trim().toLowerCase();
    return enrichedDemands.filter((d) => {
      if (hospitalFilter !== 'all' && String(d.hospital_id) !== hospitalFilter) return false;
      if (productFilter !== 'all' && String(d.product_id) !== productFilter) return false;
      if (priorityFilter !== 'all' && d.priority_level !== priorityFilter) return false;
      if (statusFilter !== 'all') {
        if (statusFilter === 'pending_approval') {
          if (!d.isPendingApproval) return false;
        } else if (d.status !== statusFilter) {
          return false;
        }
      }
      if (!q) return true;
      return (
        d.demand_code.toLowerCase().includes(q) ||
        d.hospitalCode.toLowerCase().includes(q) ||
        d.hospitalName.toLowerCase().includes(q) ||
        d.productCode.toLowerCase().includes(q) ||
        d.productName.toLowerCase().includes(q) ||
        (d.emergency_reason && d.emergency_reason.toLowerCase().includes(q))
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
    const pendingApprovalCount = demands.filter(
      (d) => d.status === 'pending_approval' || d.approval_status === 'pending_approval'
    ).length;
    const openCount = demands.filter((d) => d.status === 'open').length;
    const criticalCount = demands.filter(
      (d) => (d.status === 'open' || d.status === 'pending_approval') && d.priority_level === 'critical'
    ).length;
    const totalPendingQty = enrichedDemands.reduce((s, d) => s + Number(d.pendingQty || 0), 0);
    const totalFulfilledQty = enrichedDemands.reduce(
      (s, d) => s + Number(d.fulfilledQty || 0),
      0
    );
    const totalUnmetQty = enrichedDemands.reduce((s, d) => s + Number(d.unmetQty || 0), 0);
    return {
      pendingApprovalCount,
      openCount,
      criticalCount,
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
      header: 'Order Code',
      sortable: true,
      render: (r) => (
        <div className="flex items-center gap-1.5">
          <span className="font-bold font-mono text-slate-900">{r.demand_code}</span>
          {r.isPendingApproval && (
            <span
              className="inline-flex items-center rounded-md bg-amber-100 px-1.5 py-0.5 text-[10px] font-bold text-amber-800 border border-amber-200"
              title="Awaiting Admin Approval"
            >
              PENDING
            </span>
          )}
        </div>
      ),
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
          {r.emergency_reason && (
            <div className="text-[11px] text-amber-700 italic truncate max-w-xs" title={r.emergency_reason}>
              Note: {r.emergency_reason}
            </div>
          )}
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
          {r.isPendingApproval && (
            <>
              <button
                type="button"
                disabled={actionLoading}
                onClick={() => handleApproveOrder(r)}
                title="Approve order for LP optimization"
                className="inline-flex items-center gap-1 rounded-lg bg-emerald-600 px-2.5 py-1 text-xs font-bold text-white shadow-sm hover:bg-emerald-700 disabled:opacity-50 transition"
              >
                <CheckCircle2 className="h-3 w-3" />
                Approve
              </button>
              <button
                type="button"
                disabled={actionLoading}
                onClick={() => handleRejectOrder(r)}
                title="Reject hospital order"
                className="inline-flex items-center gap-1 rounded-lg border border-red-300 bg-white px-2 py-1 text-xs font-semibold text-red-600 hover:bg-red-50 hover:border-red-400 disabled:opacity-50 transition"
              >
                <XCircle className="h-3 w-3" />
                Reject
              </button>
            </>
          )}
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

      {/* Prominent Pending Hospital Orders Review Queue */}
      {pendingApprovalOrders.length > 0 && (
        <div className="mb-6 rounded-2xl border-2 border-amber-300 bg-gradient-to-r from-amber-50/95 via-orange-50/80 to-amber-50/95 p-5 shadow-sm">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-amber-200/80 pb-3 mb-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-500 text-white shadow-sm font-bold text-lg animate-pulse">
                ⚡
              </div>
              <div>
                <h2 className="text-base font-bold text-amber-950 flex items-center gap-2">
                  Hospital Emergency Orders Awaiting Admin Approval
                  <span className="rounded-full bg-amber-200 px-2.5 py-0.5 text-xs font-extrabold text-amber-900">
                    {pendingApprovalOrders.length} pending
                  </span>
                </h2>
                <p className="text-xs text-amber-800">
                  Hospitals submitted these emergency supply requests. Click <strong>Approve Order</strong> to make them immediately eligible for the OR-Tools LP Optimizer.
                </p>
              </div>
            </div>
            {pendingApprovalOrders.length > 1 && (
              <button
                type="button"
                onClick={() => handleApproveAll(pendingApprovalOrders)}
                disabled={actionLoading}
                className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-4 py-2 text-xs font-bold text-white shadow hover:bg-emerald-700 disabled:opacity-50 transition"
              >
                <CheckCheck className="h-4 w-4" />
                Approve All Pending ({pendingApprovalOrders.length})
              </button>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3.5">
            {pendingApprovalOrders.map((ord) => (
              <div
                key={ord.id}
                className="rounded-xl border border-amber-200 bg-white p-4 shadow-sm flex flex-col justify-between hover:shadow-md transition"
              >
                <div>
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <span className="font-mono text-xs font-bold text-slate-900 bg-slate-100 px-2 py-0.5 rounded border border-slate-200">
                      {ord.demand_code}
                    </span>
                    <div className="flex items-center gap-1.5">
                      <StatusBadge status={ord.priority_level} />
                      <span className="rounded-md bg-amber-100 px-1.5 py-0.5 text-[10px] font-bold text-amber-800">
                        PENDING
                      </span>
                    </div>
                  </div>

                  <div className="text-sm font-bold text-slate-900 mb-1">
                    {ord.productName}
                    <span className="ml-1 text-xs text-slate-500 font-normal">
                      ({ord.productCode})
                    </span>
                  </div>

                  <div className="text-xs text-slate-600 mb-2">
                    <div className="font-medium text-slate-900">
                      Quantity Requested:{' '}
                      <span className="text-base font-extrabold text-teal-700">
                        {formatNumber(ord.quantity_requested)}
                      </span>{' '}
                      {ord.productUnit}
                    </div>
                    <div className="font-medium text-slate-800 mt-1">
                      🏥 {ord.hospitalName} ({ord.hospitalCode})
                    </div>
                    <div className="text-[11px] text-slate-500">{ord.hospitalArea}</div>
                  </div>

                  {ord.emergency_reason && (
                    <div className="mb-3 rounded-lg bg-amber-50 border border-amber-200/80 px-2.5 py-1.5 text-xs text-amber-950">
                      <span className="font-bold text-amber-800">Clinical Reason:</span>{' '}
                      "{ord.emergency_reason}"
                    </div>
                  )}
                </div>

                <div className="pt-2 border-t border-slate-100 flex items-center justify-between gap-2">
                  <span className="text-[10px] text-slate-400">
                    ID #{ord.id}
                  </span>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => handleRejectOrder(ord)}
                      disabled={actionLoading}
                      className="inline-flex items-center gap-1 rounded-lg border border-red-300 bg-white px-2.5 py-1.5 text-xs font-semibold text-red-600 hover:bg-red-50 hover:border-red-400 disabled:opacity-50 transition"
                    >
                      <XCircle className="h-3.5 w-3.5" />
                      Reject
                    </button>
                    <button
                      type="button"
                      onClick={() => handleApproveOrder(ord)}
                      disabled={actionLoading}
                      className="inline-flex items-center gap-1 rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-bold text-white shadow-sm hover:bg-emerald-700 disabled:opacity-50 transition"
                    >
                      <CheckCircle2 className="h-3.5 w-3.5" />
                      Approve Order
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* KPI Strip */}
      <div className="mb-5 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Awaiting Approval"
          value={formatNumber(summary.pendingApprovalCount)}
          subtitle={
            summary.pendingApprovalCount > 0
              ? '⚡ Action required by Admin'
              : 'All hospital orders reviewed'
          }
          icon={AlertTriangle}
          accent={summary.pendingApprovalCount > 0 ? 'amber' : 'slate'}
        />
        <StatCard
          title="Open Requests"
          value={formatNumber(summary.openCount)}
          subtitle={`Approved & ready for LP run`}
          icon={ClipboardList}
          accent="teal"
        />
        <StatCard
          title="Critical Demands"
          value={formatNumber(summary.criticalCount)}
          subtitle="Tier-1 emergency priority"
          icon={Clock}
          accent="red"
        />
        <StatCard
          title="Fulfilled / Unmet"
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

      {/* Quick Status Navigation Tabs */}
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => setStatusFilter('all')}
          className={`rounded-lg px-3.5 py-1.5 text-xs font-semibold transition ${
            statusFilter === 'all'
              ? 'bg-slate-900 text-white shadow-sm'
              : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
          }`}
        >
          All Requests ({demands.length})
        </button>
        <button
          type="button"
          onClick={() => setStatusFilter('pending_approval')}
          className={`inline-flex items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-xs font-semibold transition ${
            statusFilter === 'pending_approval'
              ? 'bg-amber-600 text-white shadow-sm'
              : 'bg-amber-100 text-amber-900 hover:bg-amber-200'
          }`}
        >
          <span>⚡ Pending Approval</span>
          <span
            className={`rounded-full px-1.5 py-0.2 text-[10px] font-extrabold ${
              statusFilter === 'pending_approval' ? 'bg-amber-800 text-white' : 'bg-amber-200 text-amber-900'
            }`}
          >
            {summary.pendingApprovalCount}
          </span>
        </button>
        <button
          type="button"
          onClick={() => setStatusFilter('open')}
          className={`rounded-lg px-3.5 py-1.5 text-xs font-semibold transition ${
            statusFilter === 'open'
              ? 'bg-teal-600 text-white shadow-sm'
              : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
          }`}
        >
          Approved & Open ({summary.openCount})
        </button>
        <button
          type="button"
          onClick={() => setStatusFilter('fulfilled')}
          className={`rounded-lg px-3.5 py-1.5 text-xs font-semibold transition ${
            statusFilter === 'fulfilled'
              ? 'bg-emerald-600 text-white shadow-sm'
              : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
          }`}
        >
          Fulfilled ({demands.filter((d) => d.status === 'fulfilled').length})
        </button>
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
        defaultSortKey="isPendingApproval"
        defaultSortDir="desc"
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
