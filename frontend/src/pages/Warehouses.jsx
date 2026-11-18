import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Boxes,
  Eye,
  Gauge,
  MapPin,
  Pencil,
  Plus,
  RefreshCw,
  Search,
  Trash2,
  Warehouse as WarehouseIcon,
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
import { warehouseService } from '../services/warehouseService';
import { inventoryService } from '../services/inventoryService';
import {
  extractApiError,
  formatNumber,
  formatPercent,
  generateNextCode,
} from '../utils/formatters';

const STATUS_OPTIONS = [
  { value: 'active', label: 'Active' },
  { value: 'maintenance', label: 'Maintenance' },
  { value: 'inactive', label: 'Inactive' },
];

const INITIAL_FORM = {
  code: '',
  name: '',
  area: '',
  city: 'Pune',
  latitude: '18.5204',
  longitude: '73.8567',
  storage_capacity_units: '2500',
  status: 'active',
};

function validateWarehouseForm(form) {
  const errors = {};
  if (!form.code.trim() || form.code.trim().length < 2) {
    errors.code = 'Code must be at least 2 characters (e.g., WH-04).';
  }
  if (!form.name.trim() || form.name.trim().length < 2) {
    errors.name = 'Warehouse name must be at least 2 characters.';
  }
  if (!form.area.trim() || form.area.trim().length < 2) {
    errors.area = 'Locality / area is required.';
  }
  if (!form.city.trim()) {
    errors.city = 'City is required.';
  }
  const lat = Number(form.latitude);
  if (form.latitude === '' || Number.isNaN(lat) || lat < -90 || lat > 90) {
    errors.latitude = 'Latitude must be between -90 and 90.';
  }
  const lon = Number(form.longitude);
  if (form.longitude === '' || Number.isNaN(lon) || lon < -180 || lon > 180) {
    errors.longitude = 'Longitude must be between -180 and 180.';
  }
  const cap = Number(form.storage_capacity_units);
  if (
    form.storage_capacity_units === '' ||
    Number.isNaN(cap) ||
    !Number.isInteger(cap) ||
    cap <= 0
  ) {
    errors.storage_capacity_units = 'Storage capacity must be a positive whole number.';
  }
  return errors;
}

export default function Warehouses() {
  const toast = useToast();
  const [warehouses, setWarehouses] = useState([]);
  const [inventory, setInventory] = useState([]);
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);

  // Search & filter
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');

  // Create / Edit modal state
  const [formOpen, setFormOpen] = useState(false);
  const [editingWarehouse, setEditingWarehouse] = useState(null);
  const [form, setForm] = useState(INITIAL_FORM);
  const [fieldErrors, setFieldErrors] = useState({});
  const [submitError, setSubmitError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  // Details drawer state
  const [viewingWarehouse, setViewingWarehouse] = useState(null);

  // Delete confirmation state
  const [deletingWarehouse, setDeletingWarehouse] = useState(null);
  const [deleting, setDeleting] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const [whRows, invRows, prodRows] = await Promise.all([
        warehouseService.list(),
        inventoryService.list(),
        inventoryService.listProducts(),
      ]);
      setWarehouses(whRows);
      setInventory(invRows);
      setProducts(prodRows);
    } catch (err) {
      setLoadError(
        extractApiError(
          err,
          'Unable to load warehouses from backend API. Verify uvicorn is running.'
        )
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

  const inventoryByWarehouseId = useMemo(() => {
    const grouped = {};
    for (const item of inventory) {
      if (!grouped[item.warehouse_id]) grouped[item.warehouse_id] = [];
      grouped[item.warehouse_id].push(item);
    }
    return grouped;
  }, [inventory]);

  const warehouseStockTotals = useMemo(() => {
    const totals = {};
    for (const item of inventory) {
      totals[item.warehouse_id] =
        (totals[item.warehouse_id] || 0) + Number(item.quantity_available || 0);
    }
    return totals;
  }, [inventory]);

  const filteredWarehouses = useMemo(() => {
    const q = search.trim().toLowerCase();
    return warehouses.filter((wh) => {
      if (statusFilter !== 'all' && wh.status !== statusFilter) return false;
      if (!q) return true;
      return (
        wh.code.toLowerCase().includes(q) ||
        wh.name.toLowerCase().includes(q) ||
        wh.area.toLowerCase().includes(q) ||
        wh.city.toLowerCase().includes(q)
      );
    });
  }, [warehouses, search, statusFilter]);

  const summary = useMemo(() => {
    const totalCapacity = warehouses.reduce(
      (sum, w) => sum + Number(w.storage_capacity_units || 0),
      0
    );
    const totalStock = inventory.reduce(
      (sum, i) => sum + Number(i.quantity_available || 0),
      0
    );
    const activeCount = warehouses.filter((w) => w.status === 'active').length;
    const utilization = totalCapacity > 0 ? (totalStock / totalCapacity) * 100 : 0;
    return { totalCapacity, totalStock, activeCount, utilization };
  }, [warehouses, inventory]);

  function openCreateModal() {
    setEditingWarehouse(null);
    setForm({
      ...INITIAL_FORM,
      code: generateNextCode(
        'WH',
        warehouses.map((w) => w.code),
        2
      ),
    });
    setFieldErrors({});
    setSubmitError(null);
    setFormOpen(true);
  }

  function openEditModal(wh) {
    setEditingWarehouse(wh);
    setForm({
      code: wh.code,
      name: wh.name,
      area: wh.area,
      city: wh.city,
      latitude: String(wh.latitude),
      longitude: String(wh.longitude),
      storage_capacity_units: String(wh.storage_capacity_units),
      status: wh.status,
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
    const errors = validateWarehouseForm(form);
    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors);
      return;
    }

    setSubmitting(true);
    setSubmitError(null);
    try {
      if (editingWarehouse) {
        await warehouseService.update(editingWarehouse.id, {
          name: form.name.trim(),
          area: form.area.trim(),
          city: form.city.trim(),
          latitude: Number(form.latitude),
          longitude: Number(form.longitude),
          storage_capacity_units: Number(form.storage_capacity_units),
          status: form.status,
        });
        toast.success(
          'Warehouse updated',
          `${editingWarehouse.code} (${form.name.trim()}) saved successfully.`
        );
      } else {
        await warehouseService.create({
          code: form.code.trim().toUpperCase(),
          name: form.name.trim(),
          area: form.area.trim(),
          city: form.city.trim(),
          latitude: Number(form.latitude),
          longitude: Number(form.longitude),
          storage_capacity_units: Number(form.storage_capacity_units),
          status: form.status,
          is_synthetic_hub: true,
        });
        toast.success(
          'Warehouse created',
          `${form.code.trim().toUpperCase()} added to the logistics network.`
        );
      }
      setFormOpen(false);
      await loadData();
    } catch (err) {
      const msg = extractApiError(err, 'Failed to save warehouse.');
      setSubmitError(msg);
      toast.error('Save failed', msg);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleConfirmDelete() {
    if (!deletingWarehouse) return;
    setDeleting(true);
    try {
      await warehouseService.remove(deletingWarehouse.id);
      toast.success(
        'Warehouse deleted',
        `${deletingWarehouse.code} was permanently removed.`
      );
      if (viewingWarehouse?.id === deletingWarehouse.id) {
        setViewingWarehouse(null);
      }
      setDeletingWarehouse(null);
      await loadData();
    } catch (err) {
      const msg = extractApiError(err, 'Could not delete warehouse.');
      toast.error('Deletion blocked', msg);
      setDeletingWarehouse(null);
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
      header: 'Warehouse Name',
      sortable: true,
      render: (r) => (
        <div className="max-w-xs truncate font-medium text-slate-800" title={r.name}>
          {r.name}
        </div>
      ),
    },
    {
      key: 'area',
      header: 'Location',
      sortable: true,
      render: (r) => (
        <div>
          <span className="font-medium text-slate-800">{r.area}</span>
          <span className="ml-1 text-xs text-slate-500">({r.city})</span>
        </div>
      ),
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
      key: 'storage_capacity_units',
      header: 'Inventory / Capacity',
      sortable: true,
      sortValue: (r) => r.storage_capacity_units,
      render: (r) => {
        const stocked = warehouseStockTotals[r.id] || 0;
        const pct =
          r.storage_capacity_units > 0
            ? Math.min(100, (stocked / r.storage_capacity_units) * 100)
            : 0;
        const skuCount = (inventoryByWarehouseId[r.id] || []).length;
        return (
          <div className="min-w-[155px]">
            <div className="flex items-center justify-between text-xs">
              <span className="font-semibold text-slate-800">
                {formatNumber(stocked)} / {formatNumber(r.storage_capacity_units)}
              </span>
              <span className="text-slate-500">{skuCount} SKUs</span>
            </div>
            <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
              <div
                className={`h-full rounded-full ${
                  pct > 85 ? 'bg-orange-500' : 'bg-teal-600'
                }`}
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>
        );
      },
    },
    {
      key: 'status',
      header: 'Status',
      sortable: true,
      render: (r) => <StatusBadge status={r.status} />,
    },
    {
      key: 'actions',
      header: 'Actions',
      render: (r) => (
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={() => setViewingWarehouse(r)}
            title="View warehouse & inventory details"
            className="rounded-lg border border-slate-200 p-1.5 text-slate-600 transition hover:bg-slate-100 hover:text-slate-900"
          >
            <Eye className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            onClick={() => openEditModal(r)}
            title="Edit warehouse"
            className="rounded-lg border border-slate-200 p-1.5 text-slate-600 transition hover:border-teal-200 hover:bg-teal-50 hover:text-teal-700"
          >
            <Pencil className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            onClick={() => setDeletingWarehouse(r)}
            title="Delete warehouse"
            className="rounded-lg border border-slate-200 p-1.5 text-slate-600 transition hover:border-red-200 hover:bg-red-50 hover:text-red-600"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        </div>
      ),
    },
  ];

  const latNum = Number(form.latitude);
  const lonNum = Number(form.longitude);
  const outsidePuneBounds =
    !Number.isNaN(latNum) &&
    !Number.isNaN(lonNum) &&
    (latNum < 18.4 || latNum > 18.7 || lonNum < 73.7 || lonNum > 74.05);

  const viewedInventory = viewingWarehouse
    ? inventoryByWarehouseId[viewingWarehouse.id] || []
    : [];
  const viewedStock = viewingWarehouse
    ? warehouseStockTotals[viewingWarehouse.id] || 0
    : 0;

  return (
    <div>
      <PageHeader
        title="Warehouse Management"
        badge="Fictional Simulation Hubs"
        description="Create, inspect, update, and manage medical distribution warehouses and their live product stock across Pune and Pimpri-Chinchwad."
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
              Add Warehouse
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
          title="Total Warehouses"
          value={formatNumber(warehouses.length)}
          subtitle={`${summary.activeCount} active hubs`}
          icon={WarehouseIcon}
          accent="teal"
        />
        <StatCard
          title="Total Capacity"
          value={`${formatNumber(summary.totalCapacity)} units`}
          subtitle="Aggregate storage limit"
          icon={MapPin}
          accent="slate"
        />
        <StatCard
          title="Stocked Inventory"
          value={`${formatNumber(summary.totalStock)} units`}
          subtitle={`${inventory.length} warehouse-product rows`}
          icon={Boxes}
          accent="emerald"
        />
        <StatCard
          title="Network Utilization"
          value={formatPercent(summary.utilization)}
          subtitle="Available stock / capacity"
          icon={Gauge}
          accent={summary.utilization > 85 ? 'orange' : 'teal'}
        />
      </div>

      {/* Filter Toolbar */}
      <div className="mb-4 flex flex-col gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm sm:flex-row sm:items-center sm:justify-between">
        <div className="relative flex-1 max-w-md">
          <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by code, name, locality, or city..."
            className="w-full rounded-lg border border-slate-300 py-2 pl-9 pr-3 text-xs text-slate-900 focus:border-teal-600 focus:outline-none focus:ring-2 focus:ring-teal-600/20"
          />
        </div>
        <div className="flex items-center gap-3">
          <label className="text-xs font-semibold text-slate-600">Status:</label>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 focus:border-teal-600 focus:outline-none"
          >
            <option value="all">All Statuses</option>
            {STATUS_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
          <span className="text-xs text-slate-500">
            Showing <strong>{filteredWarehouses.length}</strong> of {warehouses.length}
          </span>
        </div>
      </div>

      <DataTable
        columns={columns}
        rows={filteredWarehouses}
        loading={loading}
        defaultSortKey="code"
        emptyMessage="No warehouses match the current search/filter criteria."
      />

      {/* Create / Edit Warehouse Modal */}
      <Modal
        open={formOpen}
        onClose={submitting ? undefined : () => setFormOpen(false)}
        title={
          editingWarehouse
            ? `Edit Warehouse — ${editingWarehouse.code}`
            : 'Add New Warehouse'
        }
        subtitle="Fictional simulation hub anchored to Pune / Pimpri-Chinchwad coordinates."
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
              form="warehouse-form"
              disabled={submitting}
              className="rounded-lg bg-teal-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-teal-700 disabled:opacity-50"
            >
              {submitting
                ? 'Saving...'
                : editingWarehouse
                ? 'Save Changes'
                : 'Create Warehouse'}
            </button>
          </>
        }
      >
        <form id="warehouse-form" onSubmit={handleFormSubmit} className="space-y-4">
          <FormErrorBanner message={submitError} />

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <TextInput
              label="Warehouse Code"
              name="code"
              value={form.code}
              onChange={handleFieldChange}
              placeholder="WH-04"
              required
              disabled={Boolean(editingWarehouse)}
              error={fieldErrors.code}
              hint={editingWarehouse ? 'Code cannot be changed after creation.' : 'Unique hub identifier.'}
            />
            <SelectInput
              label="Operational Status"
              name="status"
              value={form.status}
              onChange={handleFieldChange}
              options={STATUS_OPTIONS}
              required
            />
          </div>

          <TextInput
            label="Warehouse Name"
            name="name"
            value={form.name}
            onChange={handleFieldChange}
            placeholder="e.g., Baner West Emergency Depot (Fictional Simulation Hub)"
            required
            error={fieldErrors.name}
          />

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <TextInput
              label="Locality / Area"
              name="area"
              value={form.area}
              onChange={handleFieldChange}
              placeholder="e.g., Baner, Aundh, Hadapsar"
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
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
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
            <TextInput
              label="Storage Capacity (Units)"
              name="storage_capacity_units"
              type="number"
              min="1"
              step="1"
              value={form.storage_capacity_units}
              onChange={handleFieldChange}
              required
              error={fieldErrors.storage_capacity_units}
            />
          </div>

          {outsidePuneBounds && (
            <div className="rounded-lg border border-orange-200 bg-orange-50 px-3 py-2 text-xs text-orange-800">
              <strong>Geographical Note:</strong> Coordinates are outside the default Pune Urban &amp;
              PCMC bounding box (Lat 18.40–18.70, Lon 73.70–74.05). You may still save for wider
              Pune district expansion.
            </div>
          )}
        </form>
      </Modal>

      {/* Warehouse Details Drawer */}
      <Modal
        open={Boolean(viewingWarehouse)}
        onClose={() => setViewingWarehouse(null)}
        variant="drawer"
        title={
          viewingWarehouse
            ? `${viewingWarehouse.code} — ${viewingWarehouse.name}`
            : 'Warehouse Details'
        }
        subtitle="Live warehouse profile and product-wise inventory breakdown."
        footer={
          viewingWarehouse && (
            <>
              <button
                type="button"
                onClick={() => setViewingWarehouse(null)}
                className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
              >
                Close
              </button>
              <button
                type="button"
                onClick={() => {
                  const target = viewingWarehouse;
                  setViewingWarehouse(null);
                  openEditModal(target);
                }}
                className="rounded-lg bg-teal-600 px-4 py-2 text-xs font-semibold text-white hover:bg-teal-700"
              >
                Edit Warehouse
              </button>
            </>
          )
        }
      >
        {viewingWarehouse && (
          <div className="space-y-6">
            <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <DetailField label="Warehouse Code" value={viewingWarehouse.code} />
              <DetailField
                label="Status"
                value={<StatusBadge status={viewingWarehouse.status} />}
              />
              <DetailField label="Locality" value={viewingWarehouse.area} />
              <DetailField label="City" value={viewingWarehouse.city} />
              <DetailField
                label="Coordinates"
                value={`${viewingWarehouse.latitude.toFixed(5)}, ${viewingWarehouse.longitude.toFixed(5)}`}
              />
              <DetailField
                label="Storage Capacity"
                value={`${formatNumber(viewingWarehouse.storage_capacity_units)} units`}
              />
            </dl>

            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <div className="flex items-center justify-between text-xs">
                <span className="font-semibold text-slate-700">Capacity Utilization</span>
                <span className="font-bold text-slate-900">
                  {formatNumber(viewedStock)} / {formatNumber(viewingWarehouse.storage_capacity_units)} units (
                  {formatPercent(
                    viewingWarehouse.storage_capacity_units > 0
                      ? (viewedStock / viewingWarehouse.storage_capacity_units) * 100
                      : 0
                  )}
                  )
                </span>
              </div>
              <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-slate-200">
                <div
                  className="h-full rounded-full bg-teal-600"
                  style={{
                    width: `${Math.min(
                      100,
                      viewingWarehouse.storage_capacity_units > 0
                        ? (viewedStock / viewingWarehouse.storage_capacity_units) * 100
                        : 0
                    )}%`,
                  }}
                />
              </div>
            </div>

            <div>
              <h3 className="mb-3 text-xs font-bold uppercase tracking-wider text-slate-500">
                Current Warehouse Inventory ({viewedInventory.length} items)
              </h3>
              {viewedInventory.length === 0 ? (
                <div className="rounded-lg border border-dashed border-slate-300 p-4 text-center text-xs text-slate-500">
                  No inventory records assigned to this warehouse yet. Add stock from the Inventory
                  page.
                </div>
              ) : (
                <div className="space-y-2.5">
                  {viewedInventory.map((item) => {
                    const prod = productById[item.product_id];
                    const isLow = item.quantity_available <= item.reorder_level;
                    return (
                      <div
                        key={item.id}
                        className="flex items-center justify-between rounded-lg border border-slate-200 bg-white px-4 py-3 text-xs"
                      >
                        <div>
                          <p className="font-semibold text-slate-900">
                            {prod?.name || `Product #${item.product_id}`}
                          </p>
                          <p className="text-slate-500">
                            {item.inventory_code} &bull; Reorder Level: {formatNumber(item.reorder_level)}
                          </p>
                        </div>
                        <div className="text-right">
                          <p className="text-sm font-bold text-slate-900">
                            {formatNumber(item.quantity_available)}{' '}
                            <span className="text-xs font-normal text-slate-500">
                              {prod?.unit || 'units'}
                            </span>
                          </p>
                          <StatusBadge
                            status={isLow ? 'low_stock' : 'healthy'}
                            label={isLow ? 'Low Stock' : 'In Stock'}
                          />
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
        open={Boolean(deletingWarehouse)}
        onClose={() => setDeletingWarehouse(null)}
        onConfirm={handleConfirmDelete}
        loading={deleting}
        tone="danger"
        title="Delete Warehouse?"
        confirmLabel="Delete Warehouse"
        message={
          deletingWarehouse
            ? `Are you sure you want to delete ${deletingWarehouse.code} (${deletingWarehouse.name})? This action cannot be undone.`
            : ''
        }
        details={
          deletingWarehouse && (inventoryByWarehouseId[deletingWarehouse.id]?.length || 0) > 0
            ? `Note: This warehouse currently has ${
                inventoryByWarehouseId[deletingWarehouse.id].length
              } inventory record(s). The backend will protect referential integrity and block deletion until dependent records are removed.`
            : null
        }
      />
    </div>
  );
}
