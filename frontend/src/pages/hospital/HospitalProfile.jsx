import React, { useEffect, useState } from 'react';
import { Building2, Save } from 'lucide-react';
import {
  fetchHospitalProfile,
  updateHospitalProfile,
} from '../../services/hospitalPortalService';
import { updateCurrentProfile } from '../../services/authService';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../components/common/ToastContext';

export default function HospitalProfile() {
  const { user, refreshProfile } = useAuth();
  const { showToast } = useToast();
  const [hosp, setHosp] = useState(null);
  const [hospForm, setHospForm] = useState({ name: '', area: '', bed_capacity: 100 });
  const [userForm, setUserForm] = useState({
    full_name: user?.full_name || '',
    phone_number: user?.phone_number || '',
  });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchHospitalProfile()
      .then((data) => {
        setHosp(data);
        setHospForm({
          name: data.name || '',
          area: data.area || '',
          bed_capacity: data.bed_capacity || 100,
        });
      })
      .catch(() => showToast('Failed to load hospital profile', 'error'));
  }, []);

  async function handleSave(e) {
    e.preventDefault();
    setSaving(true);
    try {
      await Promise.all([
        updateHospitalProfile({
          name: hospForm.name.trim(),
          area: hospForm.area.trim(),
          bed_capacity: Number(hospForm.bed_capacity),
        }),
        updateCurrentProfile({
          full_name: userForm.full_name.trim(),
          phone_number: userForm.phone_number.trim() || null,
        }),
      ]);
      await refreshProfile();
      showToast('Hospital & coordinator profile updated', 'success');
    } catch (err) {
      showToast(err?.response?.data?.detail || 'Update failed', 'error');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Hospital Profile &amp; Contact</h1>
        <p className="mt-1 text-sm text-slate-500">
          Maintain accurate hospital capacity and coordinator contact details. Emergency priority
          tiers are governed by Administrators.
        </p>
      </div>

      <form
        onSubmit={handleSave}
        className="space-y-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"
      >
        <div className="flex items-center gap-3 rounded-xl bg-teal-50 p-4 text-xs text-teal-900">
          <Building2 className="h-5 w-5 text-teal-700" />
          <div>
            <p className="font-bold">
              {hosp?.code} — Priority Tier: {hosp?.priority_level?.toUpperCase()}
            </p>
            <p className="text-teal-700">
              Coordinates: {hosp?.latitude?.toFixed(4)}, {hosp?.longitude?.toFixed(4)} (Pune Scope)
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <label className="mb-1 block text-xs font-semibold text-slate-700">Hospital Name</label>
            <input
              required
              value={hospForm.name}
              onChange={(e) => setHospForm({ ...hospForm, name: e.target.value })}
              className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-semibold text-slate-700">Area / Locality</label>
            <input
              required
              value={hospForm.area}
              onChange={(e) => setHospForm({ ...hospForm, area: e.target.value })}
              className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-semibold text-slate-700">Bed Capacity</label>
            <input
              type="number"
              min={10}
              required
              value={hospForm.bed_capacity}
              onChange={(e) => setHospForm({ ...hospForm, bed_capacity: e.target.value })}
              className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
            />
          </div>
        </div>

        <hr className="border-slate-100" />

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label className="mb-1 block text-xs font-semibold text-slate-700">
              Coordinator Full Name
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
            {saving ? 'Saving...' : 'Save Changes'}
          </button>
        </div>
      </form>
    </div>
  );
}
