import React, { useEffect, useState } from 'react';
import { AlertTriangle, Save, Warehouse } from 'lucide-react';
import {
  fetchWarehouseProfile,
  updateWarehouseProfile,
  updateWarehouseStatus,
} from '../../services/warehousePortalService';
import { updateCurrentProfile } from '../../services/authService';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../components/common/ToastContext';

export default function WarehouseProfile() {
  const { user, refreshProfile } = useAuth();
  const { showToast } = useToast();
  const [wh, setWh] = useState(null);
  const [statusReason, setStatusReason] = useState('');
  const [profileForm, setProfileForm] = useState({ name: '', area: '', storage_capacity_units: 1000 });
  const [userForm, setUserForm] = useState({
    full_name: user?.full_name || '',
    phone_number: user?.phone_number || '',
  });
  const [saving, setSaving] = useState(false);

  async function load() {
    try {
      const data = await fetchWarehouseProfile();
      setWh(data);
      setProfileForm({
        name: data.name || '',
        area: data.area || '',
        storage_capacity_units: data.storage_capacity_units || 1000,
      });
    } catch {
      showToast('Failed to load warehouse profile', 'error');
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleStatusSwitch(nextStatus) {
    if (nextStatus === wh?.status) return;
    if (
      nextStatus !== 'active' &&
      !window.confirm(
        `Set warehouse ${wh?.code} to ${nextStatus.toUpperCase()}? It will be excluded from new LP optimization runs while preserving existing stock, history, and active dispatches.`
      )
    ) {
      return;
    }
    try {
      const res = await updateWarehouseStatus({
        status: nextStatus,
        reason: statusReason.trim() || `Status changed to ${nextStatus} via Warehouse Portal`,
      });
      setWh((prev) => ({ ...prev, status: res.status }));
      setStatusReason('');
      showToast(`Warehouse status updated to ${res.status.toUpperCase()}`, 'success');
    } catch (err) {
      showToast(err?.response?.data?.detail || 'Status update failed', 'error');
    }
  }

  async function handleSave(e) {
    e.preventDefault();
    setSaving(true);
    try {
      await Promise.all([
        updateWarehouseProfile({
          name: profileForm.name.trim(),
          area: profileForm.area.trim(),
          storage_capacity_units: Number(profileForm.storage_capacity_units),
        }),
        updateCurrentProfile({
          full_name: userForm.full_name.trim(),
          phone_number: userForm.phone_number.trim() || null,
        }),
      ]);
      await refreshProfile();
      showToast('Warehouse & manager details updated', 'success');
    } catch (err) {
      showToast(err?.response?.data?.detail || 'Failed to update profile', 'error');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">
          Warehouse Operational Status &amp; Profile
        </h1>
        <p className="mt-1 text-sm text-slate-500">
          Control whether this warehouse participates in new optimization runs and maintain depot
          details.
        </p>
      </div>

      {/* Operational Status Selector */}
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex items-center gap-2 text-sm font-bold text-slate-900">
          <AlertTriangle className="h-4 w-4 text-amber-600" />
          <span>Operational Availability Control ({wh?.code})</span>
        </div>
        <p className="mt-1 text-xs text-slate-500">
          Setting status to <strong>INACTIVE</strong> or <strong>MAINTENANCE</strong> excludes this
          warehouse from future LP optimization runs without erasing inventory, audit history, or
          ongoing deliveries.
        </p>

        <input
          type="text"
          value={statusReason}
          onChange={(e) => setStatusReason(e.target.value)}
          placeholder="Optional reason for status change (logged to Audit Trail)..."
          className="mt-3 w-full rounded-xl border border-slate-300 px-3 py-2 text-xs"
        />

        <div className="mt-4 grid grid-cols-3 gap-3">
          {['active', 'maintenance', 'inactive'].map((st) => {
            const selected = wh?.status === st;
            return (
              <button
                key={st}
                type="button"
                onClick={() => handleStatusSwitch(st)}
                className={`rounded-xl border px-3 py-2.5 text-xs font-bold uppercase transition ${
                  selected
                    ? st === 'active'
                      ? 'border-emerald-600 bg-emerald-600 text-white'
                      : st === 'maintenance'
                      ? 'border-amber-600 bg-amber-500 text-white'
                      : 'border-red-600 bg-red-600 text-white'
                    : 'border-slate-200 bg-white text-slate-700 hover:bg-slate-50'
                }`}
              >
                {st}
              </button>
            );
          })}
        </div>
      </div>

      {/* Profile Form */}
      <form
        onSubmit={handleSave}
        className="space-y-5 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"
      >
        <div className="flex items-center gap-2 text-sm font-bold text-slate-900">
          <Warehouse className="h-4 w-4 text-teal-600" />
          <span>Depot &amp; Manager Information</span>
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <label className="mb-1 block text-xs font-semibold text-slate-700">Warehouse Name</label>
            <input
              required
              value={profileForm.name}
              onChange={(e) => setProfileForm({ ...profileForm, name: e.target.value })}
              className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-semibold text-slate-700">Area</label>
            <input
              required
              value={profileForm.area}
              onChange={(e) => setProfileForm({ ...profileForm, area: e.target.value })}
              className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-semibold text-slate-700">
              Storage Capacity (Units)
            </label>
            <input
              type="number"
              min={100}
              required
              value={profileForm.storage_capacity_units}
              onChange={(e) =>
                setProfileForm({ ...profileForm, storage_capacity_units: e.target.value })
              }
              className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
            />
          </div>
        </div>

        <hr className="border-slate-100" />

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label className="mb-1 block text-xs font-semibold text-slate-700">
              Manager Full Name
            </label>
            <input
              required
              value={userForm.full_name}
              onChange={(e) => setUserForm({ ...userForm, full_name: e.target.value })}
              className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-semibold text-slate-700">Phone Number</label>
            <input
              value={userForm.phone_number}
              onChange={(e) => setUserForm({ ...userForm, phone_number: e.target.value })}
              className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
            />
          </div>
        </div>

        <div className="flex justify-end">
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
