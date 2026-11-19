import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertCircle, Plus, Send, Trash2 } from 'lucide-react';
import {
  createHospitalOrder,
  fetchHospitalProducts,
} from '../../services/hospitalPortalService';
import { useToast } from '../../components/common/ToastContext';

export default function HospitalCreateOrder() {
  const navigate = useNavigate();
  const { showToast } = useToast();
  const [products, setProducts] = useState([]);
  const [priority, setPriority] = useState('high');
  const [emergencyReason, setEmergencyReason] = useState('');
  const [requiredBy, setRequiredBy] = useState('');
  const [notes, setNotes] = useState('');
  const [items, setItems] = useState([{ product_id: '', quantity_requested: 25 }]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    fetchHospitalProducts()
      .then((list) => {
        setProducts(list || []);
        if (list?.length) {
          setItems([{ product_id: String(list[0].id), quantity_requested: 25 }]);
        }
      })
      .catch(() => setError('Failed to load medical product catalog.'));
  }, []);

  function addRow() {
    const firstUnused =
      products.find((p) => !items.some((i) => String(i.product_id) === String(p.id))) ||
      products[0];
    setItems((prev) => [
      ...prev,
      { product_id: firstUnused ? String(firstUnused.id) : '', quantity_requested: 20 },
    ]);
  }

  function removeRow(idx) {
    setItems((prev) => prev.filter((_, i) => i !== idx));
  }

  function updateRow(idx, field, value) {
    setItems((prev) => prev.map((row, i) => (i === idx ? { ...row, [field]: value } : row)));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    const validItems = items
      .filter((i) => i.product_id && Number(i.quantity_requested) > 0)
      .map((i) => ({
        product_id: Number(i.product_id),
        quantity_requested: parseInt(i.quantity_requested, 10),
      }));
    if (validItems.length === 0) {
      setError('Add at least one product with a positive quantity.');
      return;
    }

    setSubmitting(true);
    try {
      const res = await createHospitalOrder({
        priority_level: priority,
        emergency_reason: emergencyReason.trim() || null,
        required_by: requiredBy ? new Date(requiredBy).toISOString() : null,
        data_note: notes.trim() || null,
        items: validItems,
      });
      showToast(
        `Order ${res.order_group_code} submitted (${res.orders.length} item(s)) — pending Admin approval`,
        'success'
      );
      navigate('/hospital/orders');
    } catch (err) {
      setError(err?.response?.data?.detail || 'Failed to submit order.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Create Emergency Supply Order</h1>
        <p className="mt-1 text-sm text-slate-500">
          Request one or multiple medical supplies. Submitted orders enter{' '}
          <strong>Pending Admin Approval</strong> before entering optimization runs.
        </p>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-xl border border-red-200 bg-red-50 p-3.5 text-xs text-red-800">
          <AlertCircle className="h-4 w-4 shrink-0 text-red-600" />
          <span>{error}</span>
        </div>
      )}

      <form
        onSubmit={handleSubmit}
        className="space-y-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"
      >
        {/* Multi-product items */}
        <div>
          <div className="mb-3 flex items-center justify-between">
            <label className="text-xs font-bold uppercase tracking-wider text-slate-600">
              Requested Medical Supplies
            </label>
            <button
              type="button"
              onClick={addRow}
              className="inline-flex items-center gap-1 rounded-lg border border-teal-200 bg-teal-50 px-3 py-1.5 text-xs font-semibold text-teal-800 hover:bg-teal-100"
            >
              <Plus className="h-3.5 w-3.5" />
              Add Product Line
            </button>
          </div>

          <div className="space-y-3">
            {items.map((row, idx) => (
              <div
                key={idx}
                className="grid grid-cols-1 gap-3 rounded-xl border border-slate-200 bg-slate-50/70 p-3 sm:grid-cols-12"
              >
                <div className="sm:col-span-7">
                  <label className="mb-1 block text-[11px] font-semibold text-slate-600">
                    Medical Product
                  </label>
                  <select
                    required
                    value={row.product_id}
                    onChange={(e) => updateRow(idx, 'product_id', e.target.value)}
                    className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
                  >
                    <option value="">-- Select Product --</option>
                    {products.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.code} — {p.name} ({p.unit})
                      </option>
                    ))}
                  </select>
                </div>
                <div className="sm:col-span-4">
                  <label className="mb-1 block text-[11px] font-semibold text-slate-600">
                    Quantity
                  </label>
                  <input
                    type="number"
                    min={1}
                    required
                    value={row.quantity_requested}
                    onChange={(e) => updateRow(idx, 'quantity_requested', e.target.value)}
                    className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
                  />
                </div>
                <div className="flex items-end justify-end sm:col-span-1">
                  {items.length > 1 && (
                    <button
                      type="button"
                      onClick={() => removeRow(idx)}
                      className="rounded-lg border border-red-200 p-2 text-red-600 hover:bg-red-50"
                      title="Remove line"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label className="mb-1.5 block text-xs font-bold uppercase tracking-wider text-slate-600">
              Urgency / Priority Tier
            </label>
            <select
              value={priority}
              onChange={(e) => setPriority(e.target.value)}
              className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm font-medium"
            >
              <option value="critical">Critical (Tier 1 — Life-Critical Emergency)</option>
              <option value="high">High (Tier 2 — Urgent Surge)</option>
              <option value="normal">Normal (Tier 3 — Standard Replenishment)</option>
            </select>
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-bold uppercase tracking-wider text-slate-600">
              Required By (Optional)
            </label>
            <input
              type="datetime-local"
              value={requiredBy}
              onChange={(e) => setRequiredBy(e.target.value)}
              className="w-full rounded-xl border border-slate-300 px-3 py-2.5 text-sm"
            />
          </div>
        </div>

        <div>
          <label className="mb-1.5 block text-xs font-bold uppercase tracking-wider text-slate-600">
            Emergency Justification / Clinical Context
          </label>
          <textarea
            rows={3}
            value={emergencyReason}
            onChange={(e) => setEmergencyReason(e.target.value)}
            placeholder="e.g., ICU oxygen manifold pressure drop / emergency trauma admissions..."
            className="w-full rounded-xl border border-slate-300 p-3 text-sm focus:border-teal-600 focus:outline-none"
          />
        </div>

        <div>
          <label className="mb-1.5 block text-xs font-bold uppercase tracking-wider text-slate-600">
            Additional Delivery Notes (Optional)
          </label>
          <input
            type="text"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Receiving gate, pharmacy contact, cold-chain dock info..."
            className="w-full rounded-xl border border-slate-300 px-3 py-2.5 text-sm"
          />
        </div>

        <div className="flex items-center justify-end gap-3 border-t border-slate-100 pt-4">
          <button
            type="button"
            onClick={() => navigate('/hospital/orders')}
            className="rounded-xl border border-slate-200 px-4 py-2.5 text-xs font-semibold text-slate-700 hover:bg-slate-50"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={submitting}
            className="inline-flex items-center gap-2 rounded-xl bg-teal-600 px-5 py-2.5 text-xs font-semibold text-white shadow-sm hover:bg-teal-700 disabled:opacity-60"
          >
            <Send className="h-4 w-4" />
            {submitting ? 'Submitting Order...' : 'Submit for Admin Approval'}
          </button>
        </div>
      </form>
    </div>
  );
}
