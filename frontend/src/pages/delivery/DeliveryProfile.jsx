import React, { useState } from 'react';
import { Save, Truck } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { updateCurrentProfile } from '../../services/authService';
import { useToast } from '../../components/common/ToastContext';

export default function DeliveryProfile() {
  const { user, refreshProfile } = useAuth();
  const { showToast } = useToast();
  const [form, setForm] = useState({
    full_name: user?.full_name || '',
    phone_number: user?.phone_number || '',
  });
  const [saving, setSaving] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setSaving(true);
    try {
      await updateCurrentProfile({
        full_name: form.full_name.trim(),
        phone_number: form.phone_number.trim() || null,
      });
      await refreshProfile();
      showToast('Driver profile updated', 'success');
    } catch (err) {
      showToast(err?.response?.data?.detail || 'Update failed', 'error');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="mx-auto max-w-xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Driver Profile &amp; Assigned Fleet</h1>
        <p className="mt-1 text-sm text-slate-500">
          Keep your driver contact information up to date for hospital receiving coordination.
        </p>
      </div>

      <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-xs text-emerald-900">
        <div className="flex items-center gap-2 font-bold">
          <Truck className="h-4 w-4 text-emerald-700" />
          <span>Assigned Vehicles</span>
        </div>
        <p className="mt-1">
          {user?.assigned_vehicle_codes?.length
            ? user.assigned_vehicle_codes.join(', ')
            : 'No vehicle currently assigned. Contact an Administrator to assign a fleet vehicle.'}
        </p>
      </div>

      <form
        onSubmit={handleSubmit}
        className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"
      >
        <div>
          <label className="mb-1 block text-xs font-semibold text-slate-700">Full Name</label>
          <input
            required
            value={form.full_name}
            onChange={(e) => setForm({ ...form, full_name: e.target.value })}
            className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-semibold text-slate-700">Email</label>
          <input
            disabled
            value={user?.email || ''}
            className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-500"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-semibold text-slate-700">Phone Number</label>
          <input
            value={form.phone_number}
            onChange={(e) => setForm({ ...form, phone_number: e.target.value })}
            placeholder="+91-98XXXXXXXX"
            className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
          />
        </div>

        <div className="flex justify-end pt-2">
          <button
            type="submit"
            disabled={saving}
            className="inline-flex items-center gap-2 rounded-xl bg-navy-900 px-5 py-2.5 text-xs font-semibold text-white hover:bg-navy-800 disabled:opacity-60"
          >
            <Save className="h-4 w-4" />
            {saving ? 'Saving...' : 'Save Profile'}
          </button>
        </div>
      </form>
    </div>
  );
}
