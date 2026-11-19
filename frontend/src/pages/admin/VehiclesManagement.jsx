import React, { useEffect, useState } from 'react';
import { Plus, RefreshCw, Truck } from 'lucide-react';
import {
  createAdminVehicle,
  listAdminVehicles,
  listUsers,
  updateAdminVehicle,
} from '../../services/adminService';
import { fetchPublicOrganizations } from '../../services/authService';
import { useToast } from '../../components/common/ToastContext';

export default function VehiclesManagement() {
  const { showToast } = useToast();
  const [vehicles, setVehicles] = useState([]);
  const [drivers, setDrivers] = useState([]);
  const [warehouses, setWarehouses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);

  const [form, setForm] = useState({
    vehicle_code: '',
    warehouse_id: '',
    vehicle_type: 'medical_van',
    capacity_kg: 1200,
    status: 'available',
    assigned_driver_user_id: '',
  });

  async function load() {
    setLoading(true);
    try {
      const [vList, dList, orgs] = await Promise.all([
        listAdminVehicles(),
        listUsers({ role: 'delivery', approval_status: 'approved' }),
        fetchPublicOrganizations(),
      ]);
      setVehicles(vList || []);
      setDrivers(dList || []);
      setWarehouses(orgs?.warehouses || []);
    } catch {
      showToast('Failed to load fleet vehicles', 'error');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleAssignDriver(vehicleId, driverId) {
    try {
      await updateAdminVehicle(vehicleId, {
        assigned_driver_user_id: driverId ? Number(driverId) : null,
      });
      showToast('Driver assignment updated', 'success');
      load();
    } catch (err) {
      showToast(err?.response?.data?.detail || 'Failed to assign driver', 'error');
    }
  }

  async function handleStatusChange(vehicleId, nextStatus) {
    try {
      await updateAdminVehicle(vehicleId, { status: nextStatus });
      showToast('Vehicle status updated', 'success');
      load();
    } catch (err) {
      showToast(err?.response?.data?.detail || 'Failed to update status', 'error');
    }
  }

  async function handleCreate(e) {
    e.preventDefault();
    try {
      await createAdminVehicle({
        vehicle_code: form.vehicle_code.trim().toUpperCase(),
        warehouse_id: Number(form.warehouse_id),
        vehicle_type: form.vehicle_type,
        capacity_kg: Number(form.capacity_kg),
        status: form.status,
        assigned_driver_user_id: form.assigned_driver_user_id
          ? Number(form.assigned_driver_user_id)
          : null,
      });
      showToast('Vehicle added to fleet', 'success');
      setCreateOpen(false);
      setForm({
        vehicle_code: '',
        warehouse_id: '',
        vehicle_type: 'medical_van',
        capacity_kg: 1200,
        status: 'available',
        assigned_driver_user_id: '',
      });
      load();
    } catch (err) {
      showToast(err?.response?.data?.detail || 'Failed to add vehicle', 'error');
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Fleet Vehicles &amp; Driver Assignment</h1>
          <p className="mt-1 text-sm text-slate-500">
            Assign approved Delivery users to depot vehicles so OR-Tools dispatch plans automatically
            route to the right driver&apos;s Delivery Portal.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={load}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Refresh
          </button>
          <button
            type="button"
            onClick={() => setCreateOpen(true)}
            className="inline-flex items-center gap-1.5 rounded-lg bg-navy-900 px-4 py-2 text-xs font-semibold text-white hover:bg-navy-800"
          >
            <Plus className="h-4 w-4" />
            Add Vehicle
          </button>
        </div>
      </div>

      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-left text-xs">
            <thead className="bg-slate-50 font-semibold uppercase tracking-wider text-slate-500">
              <tr>
                <th className="px-4 py-3">Vehicle</th>
                <th className="px-4 py-3">Home Warehouse</th>
                <th className="px-4 py-3">Capacity</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Assigned Driver</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-slate-400">
                    Loading fleet...
                  </td>
                </tr>
              ) : (
                vehicles.map((v) => (
                  <tr key={v.id} className="hover:bg-slate-50/70">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <Truck className="h-4 w-4 text-teal-600" />
                        <div>
                          <p className="font-bold text-slate-900">{v.vehicle_code}</p>
                          <p className="text-[11px] text-slate-500">{v.vehicle_type}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-slate-700">
                      {v.warehouse_code} ({v.warehouse_area})
                    </td>
                    <td className="px-4 py-3 font-semibold text-slate-800">
                      {v.capacity_kg.toLocaleString()} kg
                    </td>
                    <td className="px-4 py-3">
                      <select
                        value={v.status}
                        onChange={(e) => handleStatusChange(v.id, e.target.value)}
                        className="rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-xs font-semibold text-slate-700"
                      >
                        <option value="available">Available</option>
                        <option value="maintenance">Maintenance</option>
                        <option value="unavailable">Unavailable</option>
                      </select>
                    </td>
                    <td className="px-4 py-3">
                      <select
                        value={v.assigned_driver_user_id || ''}
                        onChange={(e) => handleAssignDriver(v.id, e.target.value)}
                        className="w-56 rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-xs text-slate-800"
                      >
                        <option value="">-- Unassigned --</option>
                        {drivers.map((d) => (
                          <option key={d.id} value={d.id}>
                            {d.full_name} ({d.email})
                          </option>
                        ))}
                      </select>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {createOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
            <h3 className="text-lg font-bold text-slate-900">Add Fleet Vehicle</h3>
            <form onSubmit={handleCreate} className="mt-4 space-y-3">
              <div>
                <label className="mb-1 block text-xs font-semibold text-slate-700">
                  Vehicle Code
                </label>
                <input
                  required
                  placeholder="VEH-WH-01-03"
                  value={form.vehicle_code}
                  onChange={(e) => setForm({ ...form, vehicle_code: e.target.value })}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-semibold text-slate-700">
                  Home Warehouse
                </label>
                <select
                  required
                  value={form.warehouse_id}
                  onChange={(e) => setForm({ ...form, warehouse_id: e.target.value })}
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
                >
                  <option value="">-- Select Warehouse --</option>
                  {warehouses.map((w) => (
                    <option key={w.id} value={w.id}>
                      {w.code} — {w.name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block text-xs font-semibold text-slate-700">
                    Vehicle Type
                  </label>
                  <select
                    value={form.vehicle_type}
                    onChange={(e) => setForm({ ...form, vehicle_type: e.target.value })}
                    className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
                  >
                    <option value="medical_van">Medical Van</option>
                    <option value="cold_chain_truck">Cold-Chain Truck</option>
                    <option value="medical_truck">Medical Truck</option>
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-xs font-semibold text-slate-700">
                    Capacity (kg)
                  </label>
                  <input
                    type="number"
                    min={100}
                    required
                    value={form.capacity_kg}
                    onChange={(e) => setForm({ ...form, capacity_kg: e.target.value })}
                    className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                  />
                </div>
              </div>
              <div>
                <label className="mb-1 block text-xs font-semibold text-slate-700">
                  Assign Driver (Optional)
                </label>
                <select
                  value={form.assigned_driver_user_id}
                  onChange={(e) => setForm({ ...form, assigned_driver_user_id: e.target.value })}
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
                >
                  <option value="">-- Unassigned --</option>
                  {drivers.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.full_name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setCreateOpen(false)}
                  className="rounded-lg border border-slate-200 px-4 py-2 text-xs font-semibold text-slate-700"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="rounded-lg bg-navy-900 px-4 py-2 text-xs font-semibold text-white"
                >
                  Save Vehicle
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
