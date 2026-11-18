import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  Boxes,
  Layers,
  LayoutGrid,
  List,
  Package,
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
import { inventoryService } from '../services/inventoryService';
import { warehouseService } from '../services/warehouseService';
import {
  extractApiError,
  formatNumber,
  generateNextCode,
} from '../utils/formatters';

const INITIAL_FORM = {
  inventory_code: '',
  warehouse_id: '',
  product_id: '',
  quantity_available: '100',
  quantity_reserved: '0',
  reorder_level: '25',
  data_note: 'Manual inventory entry',
};

function validateInventoryForm(form, isEdit) {
  const errors = {};
  if (!isEdit) {
    if (!form.inventory_code.trim() || form.inventory_code.trim().length < 2) {
      errors.inventory_code = 'Inventory code must be at least 2 characters (e.g., INV-013).';
    }
    if (!form.warehouse_id) {
      errors.warehouse_id = 'Please select a warehouse.';
    }
    if (!form.product_id) {
      errors.product_id = 'Please select a medical product.';
    }
  }

  const avail = Number(form.quantity_available);
  if (
    form.quantity_available === '' ||
    Number.isNaN(avail) ||
    !Number.isInteger(avail) ||
    avail < 0
  ) {
    errors.quantity_available = 'Available stock must be a non-negative whole number (0 or greater).';
  }

  const reserved = Number(form.quantity_reserved);
  if (
    form.quantity_reserved === '' ||
    Number.isNaN(reserved) ||
    !Number.isInteger(reserved) ||
    reserved < 0
  ) {
    errors.quantity_reserved = 'Reserved stock must be a non-negative whole number.';
  } else if (!Number.isNaN(avail) && reserved > avail) {
    errors.quantity_reserved = 'Reserved stock cannot exceed available stock.';
  }

  const reorder = Number(form.reorder_level);
  if (
    form.reorder_level === '' ||
    Number.isNaN(reorder) ||
    !Number.isInteger(reorder) ||
    reorder < 0
  ) {
    errors.reorder_level = 'Reorder level must be a non-negative whole number.';
  }

  return errors;
}

export default function Inventory() {
  const toast = useToast();
  const [items, setItems] = useState([]);
  const [warehouses, setWarehouses] = useState([]);
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);

  // Filters & view mode
  const [viewMode, setViewMode] = useState('grouped'); // grouped | table
  const [search, setSearch] = useState('');
  const [warehouseFilter, setWarehouseFilter] = useState('all');
  const [productFilter, setProductFilter] = useState('all');
  const [lowStockOnly, setLowStockOnly] = useState(false);

  // Create / Edit modal state
  const [formOpen, setFormOpen] = useState(false);
  const [editingItem, setEditingItem] = useState(null);
  const [form, setForm] = useState(INITIAL_FORM);
  const [fieldErrors, setFieldErrors] = useState({});
  const [submitError, setSubmitError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  // Stock adjustment confirmation before saving edits
  const [pendingAdjustment, setPendingAdjustment] = useState(null);

  // Delete confirmation
  const [deletingItem, setDeletingItem] = useState(null);
  const [deleting, setDeleting] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const [invRows, whRows, prodRows] = await Promise.all([
        inventoryService.list(),
        warehouseService.list(),
        inventoryService.listProducts(),
      ]);
      setItems(invRows);
      setWarehouses(whRows);
      setProducts(prodRows);
    } catch (err) {
      setLoadError(
        extractApiError(err, 'Unable to load inventory records from backend API.')
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const warehouseById = useMemo(
    () => Object.fromEntries(warehouses.map((w) => [w.id, w])),
    [warehouses]
  );

  const productById = useMemo(
    () => Object.fromEntries(products.map((p) => [p.id, p])),
    [products]
  );

  const enrichedItems = useMemo(() => {
    return items.map((item) => {
      const warehouse = warehouseById[item.warehouse_id];
      const product = productById[item.product_id];
      const netAvailable = Math.max(
        0,
        Number(item.quantity_available) - Number(item.quantity_reserved)
      );
      const isLowStock = Number(item.quantity_available) <= Number(item.reorder_level);
      return {
        ...item,
        warehouseCode: warehouse?.code || `WH-#${item.warehouse_id}`,
        warehouseName: warehouse?.name || `Warehouse #${item.warehouse_id}`,
        warehouseArea: warehouse?.area || '',
        productCode: product?.code || `PROD-#${item.product_id}`,
        productName: product?.name || `Product #${item.product_id}`,
        productUnit: product?.unit || 'units',
        netAvailable,
        isLowStock,
      };
    });
  }, [items, warehouseById, productById]);

  const filteredItems = useMemo(() => {
    const q = search.trim().toLowerCase();
    return enrichedItems.filter((item) => {
      if (warehouseFilter !== 'all' && String(item.warehouse_id) !== warehouseFilter) {
        return false;
      }
      if (productFilter !== 'all' && String(item.product_id) !== productFilter) {
        return false;
      }
      if (lowStockOnly && !item.isLowStock) {
        return false;
      }
      if (!q) return true;
      return (
        item.inventory_code.toLowerCase().includes(q) ||
        item.warehouseCode.toLowerCase().includes(q) ||
        item.warehouseName.toLowerCase().includes(q) ||
        item.productCode.toLowerCase().includes(q) ||
        item.productName.toLowerCase().includes(q)
      );
    });
  }, [enrichedItems, search, warehouseFilter, productFilter, lowStockOnly]);

  const groupedByWarehouse = useMemo(() => {
    const groups = new Map();
    for (const item of filteredItems) {
      const key = item.warehouse_id;
      if (!groups.has(key)) {
        groups.set(key, {
          warehouseId: key,
          warehouseCode: item.warehouseCode,
          warehouseName: item.warehouseName,
          warehouseArea: item.warehouseArea,
          totalAvailable: 0,
          totalReserved: 0,
          lowStockCount: 0,
          records: [],
        });
      }
      const g = groups.get(key);
      g.records.push(item);
      g.totalAvailable += Number(item.quantity_available);
      g.totalReserved += Number(item.quantity_reserved);
      if (item.isLowStock) g.lowStockCount += 1;
    }
    return Array.from(groups.values()).sort((a, b) =>
      a.warehouseCode.localeCompare(b.warehouseCode)
    );
  }, [filteredItems]);

  const summary = useMemo(() => {
    const totalAvailable = enrichedItems.reduce(
      (s, i) => s + Number(i.quantity_available),
      0
    );
    const totalReserved = enrichedItems.reduce(
      (s, i) => s + Number(i.quantity_reserved),
      0
    );
    const lowStockCount = enrichedItems.filter((i) => i.isLowStock).length;

    const byProduct = products.map((prod) => {
      const matching = enrichedItems.filter((i) => i.product_id === prod.id);
      const avail = matching.reduce((s, i) => s + Number(i.quantity_available), 0);
      const low = matching.filter((i) => i.isLowStock).length;
      return {
        ...prod,
        totalAvailable: avail,
        hubCount: matching.length,
        lowStockHubs: low,
      };
    });

    return { totalAvailable, totalReserved, lowStockCount, byProduct };
  }, [enrichedItems, products]);

  function openCreateModal() {
    setEditingItem(null);
    setForm({
      ...INITIAL_FORM,
      inventory_code: generateNextCode(
        'INV',
        items.map((i) => i.inventory_code),
        3
      ),
      warehouse_id: warehouses[0] ? String(warehouses[0].id) : '',
      product_id: products[0] ? String(products[0].id) : '',
    });
    setFieldErrors({});
    setSubmitError(null);
    setFormOpen(true);
  }

  function openEditModal(item) {
    setEditingItem(item);
    setForm({
      inventory_code: item.inventory_code,
      warehouse_id: String(item.warehouse_id),
      product_id: String(item.product_id),
      quantity_available: String(item.quantity_available),
      quantity_reserved: String(item.quantity_reserved),
      reorder_level: String(item.reorder_level),
      data_note: item.data_note || '',
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
    const isEdit = Boolean(editingItem);
    const errors = validateInventoryForm(form, isEdit);
    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors);
      return;
    }

    if (isEdit) {
      // Require explicit confirmation before saving stock adjustments
      setPendingAdjustment({
        item: editingItem,
        payload: {
          quantity_available: Number(form.quantity_available),
          quantity_reserved: Number(form.quantity_reserved),
          reorder_level: Number(form.reorder_level),
          data_note: form.data_note.trim() || null,
        },
      });
      return;
    }

    setSubmitting(true);
    setSubmitError(null);
    try {
      await inventoryService.create({
        inventory_code: form.inventory_code.trim().toUpperCase(),
        warehouse_id: Number(form.warehouse_id),
        product_id: Number(form.product_id),
        quantity_available: Number(form.quantity_available),
        quantity_reserved: Number(form.quantity_reserved),
        reorder_level: Number(form.reorder_level),
        data_note: form.data_note.trim() || null,
      });
      toast.success(
        'Inventory record added',
        `${form.inventory_code.trim().toUpperCase()} persisted to database.`
      );
      setFormOpen(false);
      await loadData();
    } catch (err) {
      const msg = extractApiError(err, 'Failed to add inventory record.');
      setSubmitError(msg);
      toast.error('Create failed', msg);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleConfirmStockAdjustment() {
    if (!pendingAdjustment) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      await inventoryService.update(
        pendingAdjustment.item.id,
        pendingAdjustment.payload
      );
      toast.success(
        'Stock adjusted',
        `${pendingAdjustment.item.inventory_code} updated to ${formatNumber(
          pendingAdjustment.payload.quantity_available
        )} units.`
      );
      setPendingAdjustment(null);
      setFormOpen(false);
      await loadData();
    } catch (err) {
      const msg = extractApiError(err, 'Failed to update stock levels.');
      setSubmitError(msg);
      setPendingAdjustment(null);
      toast.error('Adjustment failed', msg);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleConfirmDelete() {
    if (!deletingItem) return;
    setDeleting(true);
    try {
      await inventoryService.remove(deletingItem.id);
      toast.success(
        'Inventory deleted',
        `${deletingItem.inventory_code} removed from warehouse stock.`
      );
      setDeletingItem(null);
      await loadData();
    } catch (err) {
      toast.error(
        'Delete failed',
        extractApiError(err, 'Could not delete inventory record.')
      );
      setDeletingItem(null);
    } finally {
      setDeleting(false);
    }
  }

  const columns = [
    {
      key: 'inventory_code',
      header: 'Code',
      sortable: true,
      render: (r) => <span className="font-semibold text-slate-900">{r.inventory_code}</span>,
    },
    {
      key: 'warehouseCode',
      header: 'Warehouse',
      sortable: true,
      render: (r) => (
        <div>
          <span className="font-semibold text-slate-800">{r.warehouseCode}</span>
          <span className="ml-1.5 text-xs text-slate-500">{r.warehouseArea}</span>
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
          <span className="ml-1.5 text-xs text-slate-400">({r.productCode})</span>
        </div>
      ),
    },
    {
      key: 'quantity_available',
      header: 'Available Stock',
      sortable: true,
      render: (r) => (
        <span className="font-bold text-slate-900">
          {formatNumber(r.quantity_available)}{' '}
          <span className="text-xs font-normal text-slate-500">{r.productUnit}</span>
        </span>
      ),
    },
    {
      key: 'quantity_reserved',
      header: 'Reserved',
      sortable: true,
      render: (r) => formatNumber(r.quantity_reserved),
    },
    {
      key: 'reorder_level',
      header: 'Reorder Level',
      sortable: true,
      render: (r) => formatNumber(r.reorder_level),
    },
    {
      key: 'stockStatus',
      header: 'Health',
      sortable: true,
      sortValue: (r) => (r.isLowStock ? 0 : 1),
      render: (r) => (
        <StatusBadge
          status={r.isLowStock ? 'low_stock' : 'healthy'}
          label={r.isLowStock ? 'Low Stock' : 'In Stock'}
        />
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
            title="Adjust stock"
            className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-2.5 py-1 text-xs font-semibold text-slate-700 transition hover:border-teal-200 hover:bg-teal-50 hover:text-teal-700"
          >
            <Pencil className="h-3 w-3" />
            Adjust
          </button>
          <button
            type="button"
            onClick={() => setDeletingItem(r)}
            title="Delete inventory record"
            className="rounded-lg border border-slate-200 p-1.5 text-slate-600 transition hover:border-red-200 hover:bg-red-50 hover:text-red-600"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        </div>
      ),
    },
  ];

  const deltaQty = pendingAdjustment
    ? pendingAdjustment.payload.quantity_available -
      Number(pendingAdjustment.item.quantity_available)
    : 0;

  return (
    <div>
      <PageHeader
        title="Inventory Management"
        badge="Synthetic Stock"
        description="Track warehouse-by-product medical stock, monitor low-stock reorder thresholds, and apply verified stock adjustments."
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
              Add Inventory
            </button>
          </>
        }
      />

      {loadError && (
        <div className="mb-5 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-xs text-red-800">
          {loadError}
        </div>
      )}

      {summary.lowStockCount > 0 && (
        <div className="mb-5 flex items-center justify-between gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-xs text-red-900">
          <div className="flex items-center gap-2.5">
            <AlertTriangle className="h-4 w-4 shrink-0 text-red-600" />
            <span>
              <strong>Low-Stock Alert:</strong> {summary.lowStockCount} warehouse inventory
              record(s) are at or below their reorder level.
            </span>
          </div>
          <button
            type="button"
            onClick={() => setLowStockOnly((prev) => !prev)}
            className="shrink-0 rounded-lg border border-red-300 bg-white px-2.5 py-1 text-xs font-semibold text-red-700 hover:bg-red-100"
          >
            {lowStockOnly ? 'Show All' : 'Filter Low Stock'}
          </button>
        </div>
      )}

      {/* Primary KPI Strip */}
      <div className="mb-5 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Total Available Stock"
          value={`${formatNumber(summary.totalAvailable)} units`}
          subtitle={`${formatNumber(summary.totalReserved)} reserved`}
          icon={Boxes}
          accent="teal"
        />
        <StatCard
          title="Active Stock Records"
          value={formatNumber(items.length)}
          subtitle={`Across ${warehouses.length} warehouses`}
          icon={Layers}
          accent="slate"
        />
        <StatCard
          title="Tracked Products"
          value={formatNumber(products.length)}
          subtitle="Essential medical supplies"
          icon={Package}
          accent="emerald"
        />
        <StatCard
          title="Low-Stock Warnings"
          value={formatNumber(summary.lowStockCount)}
          subtitle="At or below reorder threshold"
          icon={AlertTriangle}
          accent={summary.lowStockCount > 0 ? 'red' : 'emerald'}
        />
      </div>

      {/* Product-Wise Stock Summary Cards */}
      {summary.byProduct.length > 0 && (
        <div className="mb-5 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {summary.byProduct.map((prod) => (
            <div
              key={prod.id}
              className="rounded-xl border border-slate-200 bg-white px-4 py-3.5 shadow-sm"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs font-semibold text-slate-900">{prod.name}</span>
                <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-semibold text-slate-600">
                  {prod.code}
                </span>
              </div>
              <div className="mt-2 flex items-baseline justify-between">
                <p className="text-lg font-bold text-teal-700">
                  {formatNumber(prod.totalAvailable)}{' '}
                  <span className="text-xs font-normal text-slate-500">{prod.unit}s</span>
                </p>
                {prod.lowStockHubs > 0 ? (
                  <StatusBadge
                    status="low_stock"
                    label={`${prod.lowStockHubs} low`}
                  />
                ) : (
                  <span className="text-[11px] font-medium text-emerald-700">
                    {prod.hubCount} hubs stocked
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Filter & View Switcher Toolbar */}
      <div className="mb-4 flex flex-col gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm xl:flex-row xl:items-center xl:justify-between">
        <div className="relative flex-1 max-w-md">
          <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by code, warehouse, or product..."
            className="w-full rounded-lg border border-slate-300 py-2 pl-9 pr-3 text-xs text-slate-900 focus:border-teal-600 focus:outline-none focus:ring-2 focus:ring-teal-600/20"
          />
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          <select
            value={warehouseFilter}
            onChange={(e) => setWarehouseFilter(e.target.value)}
            className="rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-700 focus:border-teal-600 focus:outline-none"
          >
            <option value="all">All Warehouses</option>
            {warehouses.map((w) => (
              <option key={w.id} value={String(w.id)}>
                {w.code} — {w.area}
              </option>
            ))}
          </select>

          <select
            value={productFilter}
            onChange={(e) => setProductFilter(e.target.value)}
            className="rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-700 focus:border-teal-600 focus:outline-none"
          >
            <option value="all">All Medical Products</option>
            {products.map((p) => (
              <option key={p.id} value={String(p.id)}>
                {p.code} — {p.name}
              </option>
            ))}
          </select>

          <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50">
            <input
              type="checkbox"
              checked={lowStockOnly}
              onChange={(e) => setLowStockOnly(e.target.checked)}
              className="rounded border-slate-300 text-teal-600 focus:ring-teal-600"
            />
            Low Stock Only
          </label>

          <div className="inline-flex rounded-lg border border-slate-200 bg-slate-100 p-0.5">
            <button
              type="button"
              onClick={() => setViewMode('grouped')}
              className={`inline-flex items-center gap-1 rounded-md px-2.5 py-1 text-xs font-semibold transition ${
                viewMode === 'grouped'
                  ? 'bg-white text-teal-700 shadow-sm'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <LayoutGrid className="h-3.5 w-3.5" />
              Grouped
            </button>
            <button
              type="button"
              onClick={() => setViewMode('table')}
              className={`inline-flex items-center gap-1 rounded-md px-2.5 py-1 text-xs font-semibold transition ${
                viewMode === 'table'
                  ? 'bg-white text-teal-700 shadow-sm'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <List className="h-3.5 w-3.5" />
              Table
            </button>
          </div>
        </div>
      </div>

      {/* Grouped View or Flat Sortable Table */}
      {viewMode === 'grouped' ? (
        loading ? (
          <div className="rounded-xl border border-slate-200 bg-white p-10 text-center text-sm text-slate-500">
            Loading inventory records from MEDILOGIX API...
          </div>
        ) : groupedByWarehouse.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-300 bg-white p-10 text-center text-sm text-slate-500">
            No inventory records match the selected filters.
          </div>
        ) : (
          <div className="space-y-5">
            {groupedByWarehouse.map((group) => (
              <div
                key={group.warehouseId}
                className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm"
              >
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 bg-slate-50 px-5 py-3.5">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="rounded bg-navy-900 px-2 py-0.5 text-xs font-bold text-white">
                        {group.warehouseCode}
                      </span>
                      <h3 className="text-sm font-bold text-slate-900">
                        {group.warehouseName}
                      </h3>
                    </div>
                    <p className="mt-0.5 text-xs text-slate-500">
                      Locality: {group.warehouseArea || 'Pune'} &bull; {group.records.length}{' '}
                      stocked product(s)
                    </p>
                  </div>
                  <div className="flex items-center gap-3 text-xs">
                    <span className="font-semibold text-slate-700">
                      Total Stock:{' '}
                      <strong className="text-teal-700">
                        {formatNumber(group.totalAvailable)} units
                      </strong>
                    </span>
                    {group.lowStockCount > 0 && (
                      <StatusBadge
                        status="low_stock"
                        label={`${group.lowStockCount} Low Stock`}
                      />
                    )}
                  </div>
                </div>

                <div className="divide-y divide-slate-100">
                  {group.records.map((item) => (
                    <div
                      key={item.id}
                      className="flex flex-col gap-3 px-5 py-3.5 sm:flex-row sm:items-center sm:justify-between hover:bg-slate-50/70"
                    >
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-sm font-semibold text-slate-900">
                            {item.productName}
                          </span>
                          <span className="text-xs text-slate-400">
                            ({item.productCode} &bull; {item.inventory_code})
                          </span>
                          <StatusBadge
                            status={item.isLowStock ? 'low_stock' : 'healthy'}
                            label={item.isLowStock ? 'Low Stock' : 'In Stock'}
                          />
                        </div>
                        <p className="mt-0.5 text-xs text-slate-500">
                          Net Unreserved: <strong>{formatNumber(item.netAvailable)}</strong>{' '}
                          &bull; Reserved: {formatNumber(item.quantity_reserved)} &bull; Reorder
                          Level: {formatNumber(item.reorder_level)}
                        </p>
                      </div>

                      <div className="flex items-center gap-4">
                        <div className="text-right">
                          <p className="text-base font-bold text-slate-900">
                            {formatNumber(item.quantity_available)}{' '}
                            <span className="text-xs font-normal text-slate-500">
                              {item.productUnit}s
                            </span>
                          </p>
                        </div>
                        <div className="flex items-center gap-1.5">
                          <button
                            type="button"
                            onClick={() => openEditModal(item)}
                            className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 transition hover:border-teal-300 hover:bg-teal-50 hover:text-teal-700"
                          >
                            <Pencil className="h-3.5 w-3.5" />
                            Update Stock
                          </button>
                          <button
                            type="button"
                            onClick={() => setDeletingItem(item)}
                            title="Delete record"
                            className="rounded-lg border border-slate-200 bg-white p-1.5 text-slate-600 transition hover:border-red-200 hover:bg-red-50 hover:text-red-600"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )
      ) : (
        <DataTable
          columns={columns}
          rows={filteredItems}
          loading={loading}
          defaultSortKey="inventory_code"
          emptyMessage="No inventory records match the selected filters."
        />
      )}

      {/* Add / Update Stock Modal */}
      <Modal
        open={formOpen}
        onClose={submitting ? undefined : () => setFormOpen(false)}
        title={
          editingItem
            ? `Adjust Stock — ${editingItem.inventory_code}`
            : 'Add Inventory Record'
        }
        subtitle={
          editingItem
            ? `${editingItem.warehouseCode} • ${editingItem.productName}`
            : 'Assign product stock to a medical warehouse. Negative quantities are blocked.'
        }
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
              form="inventory-form"
              disabled={submitting}
              className="rounded-lg bg-teal-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-teal-700 disabled:opacity-50"
            >
              {submitting
                ? 'Saving...'
                : editingItem
                ? 'Review & Confirm Adjustment'
                : 'Add Inventory Record'}
            </button>
          </>
        }
      >
        <form id="inventory-form" onSubmit={handleFormSubmit} className="space-y-4">
          <FormErrorBanner message={submitError} />

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <TextInput
              label="Inventory Code"
              name="inventory_code"
              value={form.inventory_code}
              onChange={handleFieldChange}
              placeholder="INV-013"
              required
              disabled={Boolean(editingItem)}
              error={fieldErrors.inventory_code}
            />
            <SelectInput
              label="Warehouse"
              name="warehouse_id"
              value={form.warehouse_id}
              onChange={handleFieldChange}
              placeholder="Select warehouse"
              required
              disabled={Boolean(editingItem)}
              error={fieldErrors.warehouse_id}
              options={warehouses.map((w) => ({
                value: String(w.id),
                label: `${w.code} — ${w.area}`,
              }))}
            />
            <SelectInput
              label="Medical Product"
              name="product_id"
              value={form.product_id}
              onChange={handleFieldChange}
              placeholder="Select product"
              required
              disabled={Boolean(editingItem)}
              error={fieldErrors.product_id}
              options={products.map((p) => ({
                value: String(p.id),
                label: `${p.code} — ${p.name}`,
              }))}
            />
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <TextInput
              label="Available Stock"
              name="quantity_available"
              type="number"
              min="0"
              step="1"
              value={form.quantity_available}
              onChange={handleFieldChange}
              required
              error={fieldErrors.quantity_available}
              hint="Must be 0 or greater."
            />
            <TextInput
              label="Reserved Stock"
              name="quantity_reserved"
              type="number"
              min="0"
              step="1"
              value={form.quantity_reserved}
              onChange={handleFieldChange}
              required
              error={fieldErrors.quantity_reserved}
              hint="Cannot exceed available."
            />
            <TextInput
              label="Reorder Warning Level"
              name="reorder_level"
              type="number"
              min="0"
              step="1"
              value={form.reorder_level}
              onChange={handleFieldChange}
              required
              error={fieldErrors.reorder_level}
            />
          </div>

          <TextInput
            label="Operational Note"
            name="data_note"
            value={form.data_note}
            onChange={handleFieldChange}
            placeholder="Reason for stock replenishment or adjustment"
          />
        </form>
      </Modal>

      {/* Stock Adjustment Confirmation Dialog */}
      <ConfirmDialog
        open={Boolean(pendingAdjustment)}
        onClose={() => setPendingAdjustment(null)}
        onConfirm={handleConfirmStockAdjustment}
        loading={submitting}
        tone="warning"
        title="Confirm Stock Adjustment"
        confirmLabel="Confirm & Save Stock"
        message="Please verify the updated stock quantities before persisting this adjustment to the database."
        details={
          pendingAdjustment && (
            <div className="space-y-1.5">
              <p>
                <strong>Record:</strong> {pendingAdjustment.item.inventory_code} (
                {pendingAdjustment.item.warehouseCode} &bull;{' '}
                {pendingAdjustment.item.productName})
              </p>
              <p>
                <strong>Available Stock:</strong>{' '}
                {formatNumber(pendingAdjustment.item.quantity_available)} &rarr;{' '}
                <strong className="text-slate-900">
                  {formatNumber(pendingAdjustment.payload.quantity_available)}
                </strong>{' '}
                <span
                  className={`font-semibold ${
                    deltaQty >= 0 ? 'text-emerald-700' : 'text-red-600'
                  }`}
                >
                  ({deltaQty >= 0 ? `+${deltaQty}` : deltaQty})
                </span>
              </p>
              <p>
                <strong>Reserved:</strong>{' '}
                {formatNumber(pendingAdjustment.item.quantity_reserved)} &rarr;{' '}
                {formatNumber(pendingAdjustment.payload.quantity_reserved)} |{' '}
                <strong>Reorder Level:</strong>{' '}
                {formatNumber(pendingAdjustment.payload.reorder_level)}
              </p>
            </div>
          )
        }
      />

      {/* Delete Confirmation Dialog */}
      <ConfirmDialog
        open={Boolean(deletingItem)}
        onClose={() => setDeletingItem(null)}
        onConfirm={handleConfirmDelete}
        loading={deleting}
        tone="danger"
        title="Delete Inventory Record?"
        confirmLabel="Delete Record"
        message={
          deletingItem
            ? `Are you sure you want to delete ${deletingItem.inventory_code} (${deletingItem.warehouseCode} — ${deletingItem.productName})?`
            : ''
        }
      />
    </div>
  );
}
