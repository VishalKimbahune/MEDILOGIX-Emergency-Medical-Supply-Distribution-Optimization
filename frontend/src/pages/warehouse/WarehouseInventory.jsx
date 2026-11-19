import React, { useEffect, useState } from 'react';
import { ArrowDownUp, History, Plus, RefreshCw } from 'lucide-react';
import {
  adjustWarehouseStock,
  createWarehouseMedicineAndStock,
  createWarehouseStock,
  fetchWarehouseInventory,
  fetchWarehouseProducts,
  fetchWarehouseStockMovements,
} from '../../services/warehousePortalService';
import { useToast } from '../../components/common/ToastContext';

export default function WarehouseInventory() {
  const { showToast } = useToast();
  const [tab, setTab] = useState('stock');
  const [inventory, setInventory] = useState([]);
  const [movements, setMovements] = useState([]);
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);

  const [adjustTarget, setAdjustTarget] = useState(null);
  const [adjustForm, setAdjustForm] = useState({
    movement_type: 'stock_in',
    quantity_delta: 50,
    reason: '',
  });

  const [addOpen, setAddOpen] = useState(false);
  const [addForm, setAddForm] = useState({
    product_id: '',
    quantity_available: 100,
    reorder_level: 100,
    reason: 'Initial stock entry via Warehouse Portal',
  });

  const [newMedOpen, setNewMedOpen] = useState(false);
  const [newMedForm, setNewMedForm] = useState({
    name: '',
    category: 'essential_medicine',
    unit: 'box',
    unit_weight_kg: 1.5,
    base_transport_cost_per_km: 2.5,
    quantity_available: 100,
    reorder_level: 40,
    reason: 'New medicine added via Warehouse Portal',
  });

  async function load() {
    setLoading(true);
    try {
      const [inv, movs, prods] = await Promise.all([
        fetchWarehouseInventory(),
        fetchWarehouseStockMovements(),
        fetchWarehouseProducts(),
      ]);
      setInventory(inv || []);
      setMovements(movs || []);
      setProducts(prods || []);
    } catch {
      showToast('Failed to load warehouse inventory', 'error');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleAdjustSubmit(e) {
    e.preventDefault();
    if (!adjustTarget) return;
    try {
      await adjustWarehouseStock(adjustTarget.id, {
        movement_type: adjustForm.movement_type,
        quantity_delta: parseInt(adjustForm.quantity_delta, 10),
        reason: adjustForm.reason.trim(),
      });
      showToast('Stock updated & movement logged', 'success');
      setAdjustTarget(null);
      setAdjustForm({ movement_type: 'stock_in', quantity_delta: 50, reason: '' });
      load();
    } catch (err) {
      showToast(err?.response?.data?.detail || 'Stock adjustment rejected', 'error');
    }
  }

  async function handleAddSubmit(e) {
    e.preventDefault();
    try {
      await createWarehouseStock({
        product_id: Number(addForm.product_id),
        quantity_available: parseInt(addForm.quantity_available, 10),
        reorder_level: parseInt(addForm.reorder_level, 10),
        reason: addForm.reason.trim(),
      });
      showToast('Product added to warehouse inventory', 'success');
      setAddOpen(false);
      load();
    } catch (err) {
      showToast(err?.response?.data?.detail || 'Failed to add product stock', 'error');
    }
  }

  async function handleNewMedSubmit(e) {
    e.preventDefault();
    try {
      const res = await createWarehouseMedicineAndStock({
        name: newMedForm.name.trim(),
        category: newMedForm.category,
        unit: newMedForm.unit.trim() || 'box',
        unit_weight_kg: Number(newMedForm.unit_weight_kg),
        base_transport_cost_per_km: Number(newMedForm.base_transport_cost_per_km),
        quantity_available: parseInt(newMedForm.quantity_available, 10),
        reorder_level: parseInt(newMedForm.reorder_level, 10),
        reason: newMedForm.reason.trim() || 'New medicine added via Warehouse Portal',
      });
      showToast(
        `Added ${res.product.code} (${res.product.name}) with ${res.inventory.quantity_available} ${res.product.unit} in stock`,
        'success'
      );
      setNewMedOpen(false);
      setNewMedForm({
        name: '',
        category: 'essential_medicine',
        unit: 'box',
        unit_weight_kg: 1.5,
        base_transport_cost_per_km: 2.5,
        quantity_available: 100,
        reorder_level: 40,
        reason: 'New medicine added via Warehouse Portal',
      });
      load();
    } catch (err) {
      showToast(err?.response?.data?.detail || 'Failed to add new medicine', 'error');
    }
  }

  const unstockedProducts = products.filter(
    (p) => !inventory.some((i) => i.product_id === p.id)
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Inventory &amp; Stock Movements</h1>
          <p className="mt-1 text-sm text-slate-500">
            All stock-in additions and controlled adjustments require a reason and are recorded in
            immutable movement history. Negative stock is blocked.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={load}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
          {unstockedProducts.length > 0 && (
            <button
              type="button"
              onClick={() => {
                setAddForm({
                  product_id: String(unstockedProducts[0].id),
                  quantity_available: 100,
                  reorder_level: 100,
                  reason: 'Initial stock entry via Warehouse Portal',
                });
                setAddOpen(true);
              }}
              className="inline-flex items-center gap-1.5 rounded-lg border border-teal-300 bg-teal-50 px-3.5 py-2 text-xs font-semibold text-teal-900 hover:bg-teal-100"
            >
              <Plus className="h-4 w-4" />
              Stock Existing Product
            </button>
          )}
          <button
            type="button"
            onClick={() => setNewMedOpen(true)}
            className="inline-flex items-center gap-1.5 rounded-lg bg-navy-900 px-4 py-2 text-xs font-semibold text-white hover:bg-navy-800"
          >
            <Plus className="h-4 w-4" />
            Add New Medicine &amp; Stock
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-slate-200">
        <button
          type="button"
          onClick={() => setTab('stock')}
          className={`inline-flex items-center gap-1.5 border-b-2 px-4 py-2.5 text-xs font-bold ${
            tab === 'stock'
              ? 'border-teal-600 text-teal-700'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <ArrowDownUp className="h-3.5 w-3.5" />
          Current Stock ({inventory.length})
        </button>
        <button
          type="button"
          onClick={() => setTab('movements')}
          className={`inline-flex items-center gap-1.5 border-b-2 px-4 py-2.5 text-xs font-bold ${
            tab === 'movements'
              ? 'border-teal-600 text-teal-700'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <History className="h-3.5 w-3.5" />
          Movement History ({movements.length})
        </button>
      </div>

      {tab === 'stock' ? (
        <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-left text-xs">
              <thead className="bg-slate-50 font-semibold uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="px-4 py-3">Product</th>
                  <th className="px-4 py-3">Physical Stock</th>
                  <th className="px-4 py-3">Reserved</th>
                  <th className="px-4 py-3">Net Available</th>
                  <th className="px-4 py-3">Reorder Level</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {inventory.map((item) => {
                  const low = item.quantity_available <= item.reorder_level;
                  return (
                    <tr key={item.id} className="hover:bg-slate-50/70">
                      <td className="px-4 py-3">
                        <p className="font-bold text-slate-900">
                          {item.product_code} — {item.product_name}
                        </p>
                        <p className="text-[11px] text-slate-500">Unit: {item.unit}</p>
                      </td>
                      <td className="px-4 py-3 font-bold text-slate-900">
                        {item.quantity_available.toLocaleString()}
                      </td>
                      <td className="px-4 py-3 text-slate-600">
                        {item.quantity_reserved.toLocaleString()}
                      </td>
                      <td className="px-4 py-3 font-bold text-emerald-700">
                        {item.net_available.toLocaleString()}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold ${
                            low ? 'bg-amber-100 text-amber-800' : 'bg-emerald-50 text-emerald-700'
                          }`}
                        >
                          {item.reorder_level} {low ? '(LOW)' : '(OK)'}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          type="button"
                          onClick={() => {
                            setAdjustTarget(item);
                            setAdjustForm({
                              movement_type: 'stock_in',
                              quantity_delta: 50,
                              reason: '',
                            });
                          }}
                          className="rounded-lg bg-teal-600 px-3 py-1.5 text-[11px] font-semibold text-white hover:bg-teal-700"
                        >
                          Stock-In / Adjust
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-left text-xs">
              <thead className="bg-slate-50 font-semibold uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="px-4 py-3">Timestamp</th>
                  <th className="px-4 py-3">Product</th>
                  <th className="px-4 py-3">Type</th>
                  <th className="px-4 py-3">Delta</th>
                  <th className="px-4 py-3">Before &rarr; After</th>
                  <th className="px-4 py-3">Reason</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {movements.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-slate-400">
                      No stock movements recorded yet.
                    </td>
                  </tr>
                ) : (
                  movements.map((m) => (
                    <tr key={m.id}>
                      <td className="whitespace-nowrap px-4 py-2.5 text-[11px] text-slate-500">
                        {m.created_at ? new Date(m.created_at).toLocaleString() : ''}
                      </td>
                      <td className="px-4 py-2.5 font-semibold text-slate-900">
                        {m.product_code} — {m.product_name}
                      </td>
                      <td className="px-4 py-2.5 uppercase text-slate-600">{m.movement_type}</td>
                      <td
                        className={`px-4 py-2.5 font-bold ${
                          m.quantity_delta >= 0 ? 'text-emerald-700' : 'text-red-700'
                        }`}
                      >
                        {m.quantity_delta >= 0 ? `+${m.quantity_delta}` : m.quantity_delta}
                      </td>
                      <td className="px-4 py-2.5 text-slate-700">
                        {m.quantity_before} &rarr; <strong>{m.quantity_after}</strong>
                      </td>
                      <td className="px-4 py-2.5 text-slate-600">{m.reason}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Stock Adjust Modal */}
      {adjustTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
            <h3 className="text-base font-bold text-slate-900">
              Update Stock — {adjustTarget.product_name}
            </h3>
            <p className="mt-1 text-xs text-slate-500">
              Current physical stock: <strong>{adjustTarget.quantity_available}</strong>{' '}
              {adjustTarget.unit}
            </p>
            <form onSubmit={handleAdjustSubmit} className="mt-4 space-y-3">
              <div>
                <label className="mb-1 block text-xs font-semibold text-slate-700">
                  Movement Type
                </label>
                <select
                  value={adjustForm.movement_type}
                  onChange={(e) => setAdjustForm({ ...adjustForm, movement_type: e.target.value })}
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
                >
                  <option value="stock_in">Stock-In (Positive Restock)</option>
                  <option value="adjustment">Controlled Adjustment (+/-)</option>
                </select>
              </div>
              <div>
                <label className="mb-1 block text-xs font-semibold text-slate-700">
                  Quantity Delta (use negative for shrinkage/write-off)
                </label>
                <input
                  type="number"
                  required
                  value={adjustForm.quantity_delta}
                  onChange={(e) => setAdjustForm({ ...adjustForm, quantity_delta: e.target.value })}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-semibold text-slate-700">
                  Mandatory Reason (Audit Trail)
                </label>
                <textarea
                  required
                  minLength={3}
                  rows={2}
                  value={adjustForm.reason}
                  onChange={(e) => setAdjustForm({ ...adjustForm, reason: e.target.value })}
                  placeholder="e.g., Supplier batch #402 received / cycle count reconciliation..."
                  className="w-full rounded-lg border border-slate-300 p-2.5 text-sm"
                />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setAdjustTarget(null)}
                  className="rounded-lg border border-slate-200 px-4 py-2 text-xs font-semibold text-slate-700"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="rounded-lg bg-teal-600 px-4 py-2 text-xs font-semibold text-white hover:bg-teal-700"
                >
                  Record Movement
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Add Stock Modal */}
      {addOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
            <h3 className="text-base font-bold text-slate-900">Add Product to Warehouse</h3>
            <form onSubmit={handleAddSubmit} className="mt-4 space-y-3">
              <div>
                <label className="mb-1 block text-xs font-semibold text-slate-700">Product</label>
                <select
                  required
                  value={addForm.product_id}
                  onChange={(e) => setAddForm({ ...addForm, product_id: e.target.value })}
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
                >
                  {unstockedProducts.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.code} — {p.name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block text-xs font-semibold text-slate-700">
                    Initial Quantity
                  </label>
                  <input
                    type="number"
                    min={0}
                    required
                    value={addForm.quantity_available}
                    onChange={(e) => setAddForm({ ...addForm, quantity_available: e.target.value })}
                    className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs font-semibold text-slate-700">
                    Reorder Level
                  </label>
                  <input
                    type="number"
                    min={0}
                    required
                    value={addForm.reorder_level}
                    onChange={(e) => setAddForm({ ...addForm, reorder_level: e.target.value })}
                    className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                  />
                </div>
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setAddOpen(false)}
                  className="rounded-lg border border-slate-200 px-4 py-2 text-xs font-semibold text-slate-700"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="rounded-lg bg-navy-900 px-4 py-2 text-xs font-semibold text-white"
                >
                  Add Stock
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Add Brand-New Medicine & Stock Modal */}
      {newMedOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4">
          <div className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-xl">
            <h3 className="text-base font-bold text-slate-900">
              Add New Medicine / Medical Supply &amp; Stock
            </h3>
            <p className="mt-1 text-xs text-slate-500">
              Adds the medicine to the shared catalog (available for Hospitals to order &amp;
              Optimization to route) and stocks it in your warehouse immediately.
            </p>
            <form onSubmit={handleNewMedSubmit} className="mt-4 space-y-3">
              <div>
                <label className="mb-1 block text-xs font-semibold text-slate-700">
                  Medicine / Supply Name
                </label>
                <input
                  required
                  placeholder="e.g., Insulin Cold-Chain Vials / Paracetamol 500mg Packs"
                  value={newMedForm.name}
                  onChange={(e) => setNewMedForm({ ...newMedForm, name: e.target.value })}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block text-xs font-semibold text-slate-700">
                    Category
                  </label>
                  <select
                    value={newMedForm.category}
                    onChange={(e) => setNewMedForm({ ...newMedForm, category: e.target.value })}
                    className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
                  >
                    <option value="essential_medicine">Essential Medicine</option>
                    <option value="critical_care">Critical Care</option>
                    <option value="trauma_care">Trauma Care</option>
                    <option value="cold_chain">Cold-Chain / Vaccines</option>
                    <option value="medical_consumables">Consumables</option>
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-xs font-semibold text-slate-700">Unit</label>
                  <input
                    required
                    placeholder="box, vial, pack, cylinder"
                    value={newMedForm.unit}
                    onChange={(e) => setNewMedForm({ ...newMedForm, unit: e.target.value })}
                    className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                  />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="mb-1 block text-xs font-semibold text-slate-700">
                    Initial Stock
                  </label>
                  <input
                    type="number"
                    min={0}
                    required
                    value={newMedForm.quantity_available}
                    onChange={(e) =>
                      setNewMedForm({ ...newMedForm, quantity_available: e.target.value })
                    }
                    className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs font-semibold text-slate-700">
                    Reorder Level
                  </label>
                  <input
                    type="number"
                    min={0}
                    required
                    value={newMedForm.reorder_level}
                    onChange={(e) =>
                      setNewMedForm({ ...newMedForm, reorder_level: e.target.value })
                    }
                    className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs font-semibold text-slate-700">
                    Weight / Unit (kg)
                  </label>
                  <input
                    type="number"
                    step="0.1"
                    min="0.1"
                    required
                    value={newMedForm.unit_weight_kg}
                    onChange={(e) =>
                      setNewMedForm({ ...newMedForm, unit_weight_kg: e.target.value })
                    }
                    className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                  />
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setNewMedOpen(false)}
                  className="rounded-lg border border-slate-200 px-4 py-2 text-xs font-semibold text-slate-700"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="rounded-lg bg-teal-600 px-4 py-2 text-xs font-semibold text-white hover:bg-teal-700"
                >
                  Save Medicine &amp; Stock
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
