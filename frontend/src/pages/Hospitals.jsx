import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  BedDouble,
  Building2,
  Eye,
  Pencil,
  Plus,
  RefreshCw,
  Search,
  ShieldAlert,
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
  DetailField,
  FormErrorBanner,
  SelectInput,
  TextInput,
} from '../components/forms/FormFields';
import { hospitalService } from '../services/hospitalService';
import { demandService } from '../services/demandService';
import { inventoryService } from '../services/inventoryService';
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
  { value: 'active', label: 'Active' },
  { value: 'inactive', label: 'Inactive' },
];

const PRIORITY_RANK = { critical: 1, high: 2, normal: 3 };

const INITIAL_FORM = {
  code: '',
  name: '',
  area: '',
  city: 'Pune',
  priority_level: 'normal',
  bed_capacity: '200',
  latitude: '18.5308',
  longitude: '73.8475',
  status: 'active',
};

function validateHospitalForm(form) {
  const errors = {};
  if (!form.code.trim() || form.code.trim().length < 2) {
    errors.code = 'Code must be at least 2 characters (e.g., HOSP-09).';
  }
  if (!form.name.trim() || form.name.trim().length < 2) {
    errors.name = 'Hospital name must be at least 2 characters.';
  }
  if (!form.area.trim() || form.area.trim().length < 2) {
    errors.area = 'Locality / area is required.';
  }
  if (!form.city.trim()) {
    errors.city = 'City is required.';
  }
  const beds = Number(form.bed_capacity);
  if (
    form.bed_capacity === '' ||
    Number.isNaN(beds) ||
    !Number.isInteger(beds) ||
    beds <= 0
  ) {
    errors.bed_capacity = 'Bed capacity must be a positive whole number.';
  }
  const lat = Number(form.latitude);
  if (form.latitude === '' || Number.isNaN(lat) || lat < -90 || lat > 90) {
    errors.latitude = 'Latitude must be between -90 and 90.';
  }
  const lon = Number(form.longitude);
  if (form.longitude === '' || Number.isNaN(lon) || lon < -180 || lon > 180) {
    errors.longitude = 'Longitude must be between -180 and 180.';
  }
  return errors;
}

export default function Hospitals() {
  const toast = useToast();
  const [hospitals, setHospitals] = useState([]);
  const [demands, setDemands] = useState([]);
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);

  // Filters
  const [search, setSearch] = useState('');
  const [priorityFilter, setPriorityFilter] = useState('all');
  const [localityFilter, setLocalityFilter] = useState('all');

  // Form modal
  const [formOpen, setFormOpen] = useState(false);
  const [editingHospital, setEditingHospital] = useState(null);
  const [form, setForm] = useState(INITIAL_FORM);
  const [fieldErrors, setFieldErrors] = useState({});
  const [submitError, setSubmitError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  // Quick priority change tracking
  const [updatingPriorityId, setUpdatingPriorityId] = useState(null);

  // Details drawer & delete confirmation
  const [viewingHospital, setViewingHospital] = useState(null);
  const [deletingHospital, setDeletingHospital] = useState(null);
  const [deleting, setDeleting] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const [hospRows, demandRows, prodRows] = await Promise.all([
        hospitalService.list(),
        demandService.list(),
        inventoryService.listProducts(),
      ]);
      setHospitals(hospRows);
      setDemands(demandRows);
      setProducts(prodRows);
    } catch (err) {
      setLoadError(
        extractApiError(err, 'Unable to load hospitals from backend API.')
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const productById = useMemo(
    () => Object.fromEntries(products.map((p) => [p.id, p])),
    [products]
  );

  const demandsByHospitalId = useMemo(() => {
    const grouped = {};
    for (const d of demands) {
      if (!grouped[d.hospital_id]) grouped[d.hospital_id] = [];
      grouped[d.hospital_id].push(d);
    }
    return grouped;
  }, [demands]);

  const localities = useMemo(() => {
    return Array.from(new Set(hospitals.map((h) => h.area).filter(Boolean))).sort();
  }, [hospitals]);

  const filteredHospitals = useMemo(() => {
    const q = search.trim().toLowerCase();
    return hospitals.filter((h) => {
      if (priorityFilter !== 'all' && h.priority_level !== priorityFilter) return false;
      if (localityFilter !== 'all' && h.area !== localityFilter) return false;
      if (!q) return true;
      return (
        h.code.toLowerCase().includes(q) ||
        h.name.toLowerCase().includes(q) ||
        h.area.toLowerCase().includes(q) ||
        h.city.toLowerCase().includes(q)
      );
    });
  }, [hospitals, search, priorityFilter, localityFilter]);

  const summary = useMemo(() => {
    const critical = hospitals.filter((h) => h.priority_level === 'critical').length;
    const high = hospitals.filter((h) => h.priority_level === 'high').length;
    const normal = hospitals.filter((h) => h.priority_level === 'normal').length;
    const totalBeds = hospitals.reduce((s, h) => s + Number(h.bed_capacity || 0), 0);
    return { critical, high, normal, totalBeds };
  }, [hospitals]);

  function openCreateModal() {
    setEditingHospital(null);
    setForm({
      ...INITIAL_FORM,
      code: generateNextCode(
        'HOSP',
        hospitals.map((h) => h.code),
        2
      ),
    });
    setFieldErrors({});
    setSubmitError(null);
    setFormOpen(true);
  }

  function openEditModal(hosp) {
    setEditingHospital(hosp);
    setForm({
      code: hosp.code,
      name: hosp.name,
      area: hosp.area,
      city: hosp.city,
      priority_level: hosp.priority_level,
      bed_capacity: String(hosp.bed_capacity),
      latitude: String(hosp.latitude),
      longitude: String(hosp.longitude),
      status: hosp.status,
    });
    setFieldErrors({});
    setSubmitError(null);
    setFormOpen(true);
  }

  function handleFieldChange(e) {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
    if (fieldErrors[name]) {
      setFieldErrors((prev) => ({ ...prev, [name]: undefined }));
    }
  }

  async function handleFormSubmit(e) {
    e.preventDefault();
    const errors = validateHospitalForm(form);
    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors);
      return;
    }

    setSubmitting(true);
    setSubmitError(null);
    try {
      if (editingHospital) {
        await hospitalService.update(editingHospital.id, {
          name: form.name.trim(),
          area: form.area.trim(),
          city: form.city.trim(),
          priority_level: form.priority_level,
          bed_capacity: Number(form.bed_capacity),
          latitude: Number(form.latitude),
          longitude: Number(form.longitude),
          status: form.status,
        });
        toast.success(
          'Hospital updated',
          `${editingHospital.code} updated successfully.`
        );
      } else {
        await hospitalService.create({
          code: form.code.trim().toUpperCase(),
          name: form.name.trim(),
          area: form.area.trim(),
          city: form.city.trim(),
          priority_level: form.priority_level,
          bed_capacity: Number(form.bed_capacity),
          latitude: Number(form.latitude),
          longitude: Number(form.longitude),
          status: form.status,
          is_synthetic_profile: true,
        });
        toast.success(
          'Hospital registered',
          `${form.code.trim().toUpperCase()} added to the network.`
        );
      }
      setFormOpen(false);
      await loadData();
    } catch (err) {
      const msg = extractApiError(err, 'Failed to save hospital.');
      setSubmitError(msg);
      toast.error('Save failed', msg);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleQuickPriorityChange(hospital, newPriority) {
    if (hospital.priority_level === newPriority) return;
    setUpdatingPriorityId(hospital.id);
    try {
      const updated = await hospitalService.update(hospital.id, {
        priority_level: newPriority,
      });
      setHospitals((prev) =>
        prev.map((h) => (h.id === hospital.id ? updated : h))
      );
      if (viewingHospital?.id === hospital.id) {
        setViewingHospital(updated);
      }
      toast.success(
        'Priority updated',
        `${hospital.code} changed to ${newPriority.toUpperCase()} priority.`
      );
    } catch (err) {
      toast.error(
        'Priority update failed',
        extractApiError(err, 'Could not change emergency priority.')
      );
    } finally {
      setUpdatingPriorityId(null);
    }
  }

  async function handleConfirmDelete() {
    if (!deletingHospital) return;
    setDeleting(true);
    try {
      await hospitalService.remove(deletingHospital.id);
      toast.success(
        'Hospital deleted',
        `${deletingHospital.code} removed successfully.`
      );
      if (viewingHospital?.id === deletingHospital.id) {
        setViewingHospital(null);
      }
      setDeletingHospital(null);
      await loadData();
    } catch (err) {
      const msg = extractApiError(err, 'Could not delete hospital.');
      toast.error('Deletion blocked', msg);
      setDeletingHospital(null);
    } finally {
      setDeleting(false);
    }
  }

  const columns = [
    {
      key: 'code',
      header: 'Code',
      sortable: true,
      render: (r) => <span className="font-semibold text-slate-900">{r.code}</span>,
    },
    {
      key: 'name',
      header: 'Hospital Profile (Synthetic)',
      sortable: true,
      render: (r) => (
        <div className="max-w-xs truncate font-medium text-slate-800" title={r.name}>
          {r.name}
        </div>
      ),
    },
    {
      key: 'area',
      header: 'Locality',
      sortable: true,
      render: (r) => (
        <span>
          {r.area} <span className="text-xs text-slate-400">({r.city})</span>
        </span>
      ),
    },
    {
      key: 'priority_level',
      header: 'Emergency Priority',
      sortable: true,
      sortValue: (r) => PRIORITY_RANK[r.priority_level] || 99,
      render: (r) => (
        <div className="flex items-center gap-2">
          <StatusBadge status={r.priority_level} />
          <select
            aria-label={`Change priority for ${r.code}`}
            value={r.priority_level}
            disabled={updatingPriorityId === r.id}
            onChange={(e) => handleQuickPriorityChange(r, e.target.value)}
            className="rounded-md border border-slate-200 bg-white px-2 py-1 text-[11px] font-medium text-slate-700 hover:border-slate-300 focus:border-teal-600 focus:outline-none disabled:opacity-50"
          >
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="normal">Normal</option>
          </select>
        </div>
      ),
    },
    {
      key: 'bed_capacity',
      header: 'Beds',
      sortable: true,
      render: (r) => formatNumber(r.bed_capacity),
    },
    {
      key: 'coords',
      header: 'Coordinates',
      render: (r) => (
        <span className="font-mono text-xs text-slate-600">
          {r.latitude.toFixed(4)}, {r.longitude.toFixed(4)}
        </span>
      ),
    },
    {
      key: 'actions',
      header: 'Actions',
      render: (r) => (
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={() => setViewingHospital(r)}
            title="View hospital details"
            className="rounded-lg border border-slate-200 p-1.5 text-slate-600 transition hover:bg-slate-100 hover:text-slate-900"
          >
            <Eye className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            onClick={() => openEditModal(r)}
            title="Edit hospital"
            className="rounded-lg border border-slate-200 p-1.5 text-slate-600 transition hover:border-teal-200 hover:bg-teal-50 hover:text-teal-700"
          >
            <Pencil className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            onClick={() => setDeletingHospital(r)}
            title="Delete hospital"
            className="rounded-lg border border-slate-200 p-1.5 text-slate-600 transition hover:border-red-200 hover:bg-red-50 hover:text-red-600"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        </div>
      ),
    },
  ];

  const viewedDemands = viewingHospital
    ? demandsByHospitalId[viewingHospital.id] || []
    : [];

  return (
    <div>
      <PageHeader
        title="Hospital Management"
        badge="Priority Tiers"
        description="Register hospitals, manage emergency priority tiers (Critical, High, Normal), and inspect open supply demands."
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
              Register Hospital
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
      <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Total Hospitals"
          value={formatNumber(hospitals.length)}
          subtitle={`${localities.length} Pune / PCMC localities`}
          icon={Building2}
          accent="teal"
        />
        <StatCard
          title="Critical Priority"
          value={formatNumber(summary.critical)}
          subtitle="Lexicographic Stage 1"
          icon={AlertTriangle}
          accent="red"
        />
        <StatCard
          title="High Priority"
          value={formatNumber(summary.high)}
          subtitle={`${summary.normal} Normal tier hospitals`}
          icon={ShieldAlert}
          accent="orange"
        />
        <StatCard
          title="Synthetic Bed Capacity"
          value={formatNumber(summary.totalBeds)}
          subtitle="Total network capacity"
          icon={BedDouble}
          accent="emerald"
        />
      </div>

      {/* Filter Toolbar */}
      <div className="mb-4 flex flex-col gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm lg:flex-row lg:items-center lg:justify-between">
        <div className="relative flex-1 max-w-md">
          <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by hospital code, name, or locality..."
            className="w-full rounded-lg border border-slate-300 py-2 pl-9 pr-3 text-xs text-slate-900 focus:border-teal-600 focus:outline-none focus:ring-2 focus:ring-teal-600/20"
          />
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-1.5">
            <label className="text-xs font-semibold text-slate-600">Locality:</label>
            <select
              value={localityFilter}
              onChange={(e) => setLocalityFilter(e.target.value)}
              className="rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-700 focus:border-teal-600 focus:outline-none"
            >
              <option value="all">All Localities</option>
              {localities.map((area) => (
                <option key={area} value={area}>
                  {area}
                </option>
              ))}
            </select>
          </div>
          <div className="flex items-center gap-1.5">
            <label className="text-xs font-semibold text-slate-600">Priority:</label>
            <select
              value={priorityFilter}
              onChange={(e) => setPriorityFilter(e.target.value)}
              className="rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-700 focus:border-teal-600 focus:outline-none"
            >
              <option value="all">All Tiers</option>
              <option value="critical">Critical</option>
              <option value="high">High</option>
              <option value="normal">Normal</option>
            </select>
          </div>
          <span className="text-xs text-slate-500">
            Showing <strong>{filteredHospitals.length}</strong> of {hospitals.length}
          </span>
        </div>
      </div>

      <DataTable
        columns={columns}
        rows={filteredHospitals}
        loading={loading}
        defaultSortKey="code"
        emptyMessage="No hospitals match the selected search or filters."
      />

      {/* Register / Edit Hospital Modal */}
      <Modal
        open={formOpen}
        onClose={submitting ? undefined : () => setFormOpen(false)}
        title={
          editingHospital
            ? `Edit Hospital — ${editingHospital.code}`
            : 'Register Hospital Profile'
        }
        subtitle="Synthetic operational profile anchored to Pune / Pimpri-Chinchwad locality coordinates."
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
              form="hospital-form"
              disabled={submitting}
              className="rounded-lg bg-teal-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-teal-700 disabled:opacity-50"
            >
              {submitting
                ? 'Saving...'
                : editingHospital
                ? 'Save Changes'
                : 'Register Hospital'}
            </button>
          </>
        }
      >
        <form id="hospital-form" onSubmit={handleFormSubmit} className="space-y-4">
          <FormErrorBanner message={submitError} />

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <TextInput
              label="Hospital Code"
              name="code"
              value={form.code}
              onChange={handleFieldChange}
              placeholder="HOSP-09"
              required
              disabled={Boolean(editingHospital)}
              error={fieldErrors.code}
            />
            <SelectInput
              label="Emergency Priority Tier"
              name="priority_level"
              value={form.priority_level}
              onChange={handleFieldChange}
              options={PRIORITY_OPTIONS}
              required
            />
          </div>

          <TextInput
            label="Hospital Name"
            name="name"
            value={form.name}
            onChange={handleFieldChange}
            placeholder="e.g., Wakad Emergency Care Center (Synthetic Profile)"
            required
            error={fieldErrors.name}
          />

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <TextInput
              label="Locality / Area"
              name="area"
              value={form.area}
              onChange={handleFieldChange}
              placeholder="e.g., Aundh, Kothrud"
              required
              error={fieldErrors.area}
            />
            <TextInput
              label="City"
              name="city"
              value={form.city}
              onChange={handleFieldChange}
              placeholder="Pune"
              required
              error={fieldErrors.city}
            />
            <SelectInput
              label="Status"
              name="status"
              value={form.status}
              onChange={handleFieldChange}
              options={STATUS_OPTIONS}
              required
            />
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <TextInput
              label="Bed Capacity"
              name="bed_capacity"
              type="number"
              min="1"
              step="1"
              value={form.bed_capacity}
              onChange={handleFieldChange}
              required
              error={fieldErrors.bed_capacity}
            />
            <TextInput
              label="Latitude"
              name="latitude"
              type="number"
              step="any"
              value={form.latitude}
              onChange={handleFieldChange}
              required
              error={fieldErrors.latitude}
            />
            <TextInput
              label="Longitude"
              name="longitude"
              type="number"
              step="any"
              value={form.longitude}
              onChange={handleFieldChange}
              required
              error={fieldErrors.longitude}
            />
          </div>
        </form>
      </Modal>

      {/* Hospital Details Drawer */}
      <Modal
        open={Boolean(viewingHospital)}
        onClose={() => setViewingHospital(null)}
        variant="drawer"
        title={
          viewingHospital
            ? `${viewingHospital.code} — ${viewingHospital.name}`
            : 'Hospital Details'
        }
        subtitle="Complete hospital profile, priority controls, and active supply demands."
        footer={
          viewingHospital && (
            <>
              <button
                type="button"
                onClick={() => setViewingHospital(null)}
                className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
              >
                Close
              </button>
              <button
                type="button"
                onClick={() => {
                  const target = viewingHospital;
                  setViewingHospital(null);
                  openEditModal(target);
                }}
                className="rounded-lg bg-teal-600 px-4 py-2 text-xs font-semibold text-white hover:bg-teal-700"
              >
                Edit Hospital
              </button>
            </>
          )
        }
      >
        {viewingHospital && (
          <div className="space-y-6">
            <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <DetailField label="Hospital Code" value={viewingHospital.code} />
              <DetailField
                label="Status"
                value={<StatusBadge status={viewingHospital.status} />}
              />
              <DetailField label="Locality" value={viewingHospital.area} />
              <DetailField label="City" value={viewingHospital.city} />
              <DetailField
                label="Bed Capacity"
                value={`${formatNumber(viewingHospital.bed_capacity)} beds`}
              />
              <DetailField
                label="Coordinates"
                value={`${viewingHospital.latitude.toFixed(5)}, ${viewingHospital.longitude.toFixed(5)}`}
              />
            </dl>

            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-xs font-semibold text-slate-700">
                Quick Emergency Priority Adjustment
              </p>
              <p className="mt-0.5 text-[11px] text-slate-500">
                Determines lexicographic optimization tier during supply shortages.
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                {['critical', 'high', 'normal'].map((tier) => {
                  const active = viewingHospital.priority_level === tier;
                  const activeClass =
                    tier === 'critical'
                      ? 'bg-red-600 text-white border-red-600'
                      : tier === 'high'
                      ? 'bg-orange-500 text-white border-orange-500'
                      : 'bg-emerald-600 text-white border-emerald-600';
                  return (
                    <button
                      key={tier}
                      type="button"
                      disabled={updatingPriorityId === viewingHospital.id}
                      onClick={() => handleQuickPriorityChange(viewingHospital, tier)}
                      className={`rounded-lg border px-3 py-1.5 text-xs font-semibold capitalize transition ${
                        active
                          ? activeClass
                          : 'border-slate-300 bg-white text-slate-700 hover:bg-slate-100'
                      }`}
                    >
                      {tier}
                    </button>
                  );
                })}
              </div>
            </div>

            <div>
              <h3 className="mb-3 text-xs font-bold uppercase tracking-wider text-slate-500">
                Demand Requests ({viewedDemands.length})
              </h3>
              {viewedDemands.length === 0 ? (
                <div className="rounded-lg border border-dashed border-slate-300 p-4 text-center text-xs text-slate-500">
                  No demand requests recorded for this hospital.
                </div>
              ) : (
                <div className="space-y-2">
                  {viewedDemands.map((dem) => {
                    const prod = productById[dem.product_id];
                    return (
                      <div
                        key={dem.id}
                        className="flex items-center justify-between rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-xs"
                      >
                        <div>
                          <p className="font-semibold text-slate-900">
                            {prod?.name || `Product #${dem.product_id}`}
                          </p>
                          <p className="text-slate-500">{dem.demand_code}</p>
                        </div>
                        <div className="flex items-center gap-2.5">
                          <span className="font-bold text-slate-900">
                            {formatNumber(dem.quantity_requested)} {prod?.unit || 'units'}
                          </span>
                          <StatusBadge status={dem.status} />
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        )}
      </Modal>

      {/* Delete Confirmation Dialog */}
      <ConfirmDialog
        open={Boolean(deletingHospital)}
        onClose={() => setDeletingHospital(null)}
        onConfirm={handleConfirmDelete}
        loading={deleting}
        tone="danger"
        title="Delete Hospital?"
        confirmLabel="Delete Hospital"
        message={
          deletingHospital
            ? `Are you sure you want to delete ${deletingHospital.code} (${deletingHospital.name})?`
            : ''
        }
        details={
          deletingHospital && (demandsByHospitalId[deletingHospital.id]?.length || 0) > 0
            ? `Note: This hospital has ${
                demandsByHospitalId[deletingHospital.id].length
              } demand request(s). The backend will block deletion while dependent demands, routes, or allocations exist.`
            : null
        }
      />
    </div>
  );
}
