import React, { useEffect, useState } from 'react';
import { Cpu, PackageCheck, RefreshCw, Truck } from 'lucide-react';
import {
  fetchWarehouseAllocations,
  fetchWarehouseShipments,
  updateShipmentPreparation,
} from '../../services/warehousePortalService';
import { useToast } from '../../components/common/ToastContext';

const PREP_STAGES = [
  { value: 'pending', label: 'Pending' },
  { value: 'preparing', label: 'Preparing' },
  { value: 'ready_for_dispatch', label: 'Ready for Dispatch' },
  { value: 'handed_over', label: 'Handed Over to Driver' },
];

export default function WarehouseShipments() {
  const { showToast } = useToast();
  const [tab, setTab] = useState('shipments');
  const [shipments, setShipments] = useState([]);
  const [allocations, setAllocations] = useState({ run_code: null, allocations: [] });
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    try {
      const [ships, allocs] = await Promise.all([
        fetchWarehouseShipments(),
        fetchWarehouseAllocations(),
      ]);
      setShipments(ships || []);
      setAllocations(allocs || { run_code: null, allocations: [] });
    } catch {
      showToast('Failed to load shipments and allocations', 'error');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handlePrepChange(assignmentId, prepStatus) {
    try {
      await updateShipmentPreparation(assignmentId, {
        preparation_status: prepStatus,
      });
      showToast(`Shipment marked '${prepStatus.replace(/_/g, ' ')}'`, 'success');
      load();
    } catch (err) {
      showToast(err?.response?.data?.detail || 'Failed to update preparation status', 'error');
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">
            Outgoing Shipments &amp; Optimization Allocations
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Pack assigned medical supply loads and coordinate smooth handover to assigned delivery
            drivers.
          </p>
        </div>
        <button
          type="button"
          onClick={load}
          className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      <div className="flex gap-2 border-b border-slate-200">
        <button
          type="button"
          onClick={() => setTab('shipments')}
          className={`inline-flex items-center gap-1.5 border-b-2 px-4 py-2.5 text-xs font-bold ${
            tab === 'shipments'
              ? 'border-teal-600 text-teal-700'
              : 'border-transparent text-slate-500'
          }`}
        >
          <PackageCheck className="h-3.5 w-3.5" />
          Outgoing Dispatches ({shipments.length})
        </button>
        <button
          type="button"
          onClick={() => setTab('allocations')}
          className={`inline-flex items-center gap-1.5 border-b-2 px-4 py-2.5 text-xs font-bold ${
            tab === 'allocations'
              ? 'border-teal-600 text-teal-700'
              : 'border-transparent text-slate-500'
          }`}
        >
          <Cpu className="h-3.5 w-3.5" />
          Latest LP Allocations ({allocations.allocations?.length || 0})
        </button>
      </div>

      {tab === 'shipments' ? (
        shipments.length === 0 ? (
          <div className="rounded-2xl border border-slate-200 bg-white p-12 text-center text-sm text-slate-500">
            No outgoing dispatch assignments for your warehouse yet.
          </div>
        ) : (
          <div className="space-y-4">
            {shipments.map((s) => (
              <div
                key={s.assignment_id}
                className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <Truck className="h-4 w-4 text-teal-600" />
                      <span className="font-mono text-sm font-bold text-navy-900">
                        {s.plan_code}
                      </span>
                      <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-[10px] font-bold text-slate-700">
                        {s.vehicle_code} (Wave {s.trip_number})
                      </span>
                      <span className="rounded-full bg-sky-100 px-2.5 py-0.5 text-[10px] font-bold uppercase text-sky-800">
                        Dispatch: {s.dispatch_status}
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-slate-600">
                      Driver: <strong>{s.driver_name}</strong> &bull; Load:{' '}
                      <strong>
                        {s.total_load_kg} / {s.capacity_kg} kg ({s.utilization_pct}%)
                      </strong>
                    </p>
                  </div>

                  <div className="flex items-center gap-2">
                    <label className="text-[11px] font-semibold text-slate-500">
                      Prep Status:
                    </label>
                    <select
                      value={s.preparation_status}
                      onChange={(e) => handlePrepChange(s.assignment_id, e.target.value)}
                      className="rounded-lg border border-teal-300 bg-teal-50 px-3 py-1.5 text-xs font-bold text-teal-900"
                    >
                      {PREP_STAGES.map((st) => (
                        <option key={st.value} value={st.value}>
                          {st.label}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
                  {(s.stops || []).map((stop) => (
                    <div
                      key={stop.stop_id}
                      className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-slate-900">
                          Stop #{stop.stop_sequence}: {stop.hospital_code} — {stop.hospital_name}
                        </span>
                        <span className="rounded bg-white px-2 py-0.5 text-[10px] font-bold uppercase text-slate-700 ring-1 ring-slate-200">
                          {stop.status}
                        </span>
                      </div>
                      <ul className="mt-2 space-y-1 text-[11px] text-slate-600">
                        {(stop.shipment_lines || []).map((ln, i) => (
                          <li key={i} className="flex justify-between">
                            <span>{ln.product_name}</span>
                            <span className="font-semibold text-slate-800">
                              {ln.quantity_planned} {ln.unit}
                            </span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )
      ) : (
        <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div className="border-b border-slate-100 bg-slate-50 px-4 py-3 text-xs text-slate-600">
            Latest Optimal Run: <strong>{allocations.run_code || 'None yet'}</strong> (
            {allocations.model_type || '—'})
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-left text-xs">
              <thead className="bg-slate-50 font-semibold uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="px-4 py-3">Destination Hospital</th>
                  <th className="px-4 py-3">Product</th>
                  <th className="px-4 py-3">Quantity Allocated</th>
                  <th className="px-4 py-3">Est. Transport Cost</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {(allocations.allocations || []).map((a, idx) => (
                  <tr key={idx}>
                    <td className="px-4 py-2.5 font-semibold text-slate-900">
                      {a.hospital_code} — {a.hospital_name}
                    </td>
                    <td className="px-4 py-2.5 text-slate-700">
                      {a.product_code} — {a.product_name}
                    </td>
                    <td className="px-4 py-2.5 font-bold text-teal-700">
                      {a.quantity_allocated} {a.unit}
                    </td>
                    <td className="px-4 py-2.5 text-slate-600">
                      INR {Number(a.transport_cost || 0).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
