import React, { useEffect, useMemo, useState } from 'react';
import {
  CheckCircle2,
  MapPin,
  Navigation,
  Play,
  RefreshCw,
  Truck,
} from 'lucide-react';
import {
  confirmDeliveryStop,
  fetchDeliveryAssignments,
  updateDeliveryStopStatus,
} from '../../services/deliveryPortalService';
import PuneNetworkMap from '../../components/maps/PuneNetworkMap';
import { useToast } from '../../components/common/ToastContext';

export default function DeliveryAssignments() {
  const { showToast } = useToast();
  const [assignments, setAssignments] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [loading, setLoading] = useState(true);

  // Delivery Confirmation Modal
  const [confirmStop, setConfirmStop] = useState(null);
  const [confirmItems, setConfirmItems] = useState({});
  const [confirmRemarks, setConfirmRemarks] = useState('');
  const [submitting, setSubmitting] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const list = await fetchDeliveryAssignments();
      setAssignments(list || []);
      if (list?.length && !selectedId) {
        setSelectedId(list[0].id);
      }
    } catch {
      showToast('Failed to load assigned routes', 'error');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  const selected = useMemo(
    () => assignments.find((a) => a.id === selectedId) || assignments[0] || null,
    [assignments, selectedId]
  );

  const mapProps = useMemo(() => {
    if (!selected) return null;
    const whMarker = {
      id: selected.warehouse_id,
      code: selected.warehouse_code,
      name: selected.warehouse_name,
      area: selected.warehouse_area || 'Pune',
      latitude: selected.warehouse_lat,
      longitude: selected.warehouse_lon,
      status: 'active',
    };
    const hospMarkers = (selected.stops || []).map((s) => ({
      id: s.hospital_id,
      code: s.hospital_code,
      name: s.hospital_name,
      area: s.hospital_area,
      priority_level: s.priority_level,
      latitude: s.latitude,
      longitude: s.longitude,
    }));
    const routeObj = {
      vehicle_code: selected.vehicle_code,
      vehicle_type: selected.vehicle_type,
      warehouse_code: selected.warehouse_code,
      trip_number: selected.trip_number,
      route_distance_km: selected.route_distance_km,
      estimated_duration_min: selected.estimated_duration_min,
      total_load_kg: selected.total_load_kg,
      capacity_kg: selected.capacity_kg,
      utilization_pct: selected.utilization_pct,
      routing_source: selected.routing_source,
      routing_objective: selected.routing_objective,
      route_geometry: selected.route_geometry || [],
      route_coordinates: selected.route_coordinates || [],
      road_names: selected.road_names || [],
      delivery_stops: selected.stops || [],
    };
    return {
      warehouses: whMarker.latitude ? [whMarker] : [],
      hospitals: hospMarkers,
      vehicleRoutes: [routeObj],
      routingSource: selected.routing_source,
      routingObjective: selected.routing_objective,
    };
  }, [selected]);

  async function handleQuickStopStatus(stopId, nextStatus) {
    try {
      const updated = await updateDeliveryStopStatus(stopId, { status: nextStatus });
      setAssignments((prev) => prev.map((a) => (a.id === updated.id ? updated : a)));
      showToast(`Stop marked '${nextStatus.replace(/_/g, ' ')}'`, 'success');
    } catch (err) {
      showToast(err?.response?.data?.detail || 'Status transition rejected', 'error');
    }
  }

  function openConfirmModal(stop) {
    const init = {};
    (stop.shipment_lines || []).forEach((ln) => {
      init[ln.id] = ln.quantity_planned;
    });
    setConfirmStop(stop);
    setConfirmItems(init);
    setConfirmRemarks('');
  }

  async function handleConfirmSubmit(e) {
    e.preventDefault();
    if (!confirmStop) return;
    setSubmitting(true);
    try {
      const itemsPayload = (confirmStop.shipment_lines || []).map((ln) => ({
        shipment_line_id: ln.id,
        quantity_delivered: Number(confirmItems[ln.id] ?? 0),
      }));
      const updated = await confirmDeliveryStop(confirmStop.id, {
        remarks: confirmRemarks.trim() || null,
        items: itemsPayload,
      });
      setAssignments((prev) => prev.map((a) => (a.id === updated.id ? updated : a)));
      showToast('Delivery confirmation recorded', 'success');
      setConfirmStop(null);
    } catch (err) {
      showToast(err?.response?.data?.detail || 'Delivery confirmation failed', 'error');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Assigned Routes &amp; Delivery Map</h1>
          <p className="mt-1 text-sm text-slate-500">
            Follow your assigned OpenStreetMap road corridor and record full or partial delivery
            confirmations at each hospital stop.
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

      {assignments.length === 0 ? (
        <div className="rounded-2xl border border-slate-200 bg-white p-12 text-center text-sm text-slate-500">
          No delivery assignments found for your account yet.
        </div>
      ) : (
        <>
          {/* Route Selector Pills */}
          <div className="flex flex-wrap gap-2">
            {assignments.map((a) => (
              <button
                key={a.id}
                type="button"
                onClick={() => setSelectedId(a.id)}
                className={`rounded-xl border px-4 py-2 text-left text-xs transition ${
                  selected?.id === a.id
                    ? 'border-navy-900 bg-navy-900 text-white shadow-sm'
                    : 'border-slate-200 bg-white text-slate-700 hover:bg-slate-50'
                }`}
              >
                <div className="flex items-center gap-2 font-bold">
                  <Truck className="h-3.5 w-3.5" />
                  <span>
                    {a.plan_code} &bull; {a.vehicle_code} (W{a.trip_number})
                  </span>
                </div>
                <p className="mt-0.5 text-[10px] opacity-80">
                  {a.stops?.length || 0} stops &bull; {a.status.replace('_', ' ')}
                </p>
              </button>
            ))}
          </div>

          {/* Interactive OSM Map for Selected Route */}
          {selected && mapProps && (
            <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <PuneNetworkMap
                {...mapProps}
                title={`Assigned Route: ${selected.vehicle_code} (${selected.plan_code})`}
                subtitle="Directed Pune OpenStreetMap route geometry — Estimated travel time uses assumed road-class speeds (not live GPS/traffic)"
                heightClass="h-[340px]"
              />
            </div>
          )}

          {/* Ordered Hospital Stops */}
          {selected && (
            <div className="space-y-4">
              <h2 className="text-base font-bold text-slate-900">
                Ordered Hospital Delivery Stops ({selected.stops?.length || 0})
              </h2>
              {(selected.stops || []).map((stop) => {
                const isDone = stop.status === 'delivered' || stop.status === 'cancelled';
                return (
                  <div
                    key={stop.id}
                    className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="flex h-6 w-6 items-center justify-center rounded-full bg-navy-900 text-xs font-bold text-white">
                            {stop.stop_sequence}
                          </span>
                          <span className="text-sm font-bold text-slate-900">
                            {stop.hospital_code} — {stop.hospital_name}
                          </span>
                          <span
                            className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase ${
                              stop.priority_level === 'critical'
                                ? 'bg-red-100 text-red-800'
                                : stop.priority_level === 'high'
                                ? 'bg-amber-100 text-amber-800'
                                : 'bg-slate-100 text-slate-700'
                            }`}
                          >
                            {stop.priority_level}
                          </span>
                          <span className="rounded-full bg-sky-100 px-2.5 py-0.5 text-[10px] font-bold uppercase text-sky-800">
                            {stop.status.replace('_', ' ')}
                          </span>
                        </div>
                        <p className="mt-1 flex flex-wrap items-center gap-3 text-xs text-slate-500">
                          <span className="inline-flex items-center gap-1">
                            <MapPin className="h-3.5 w-3.5 text-teal-600" />
                            {stop.hospital_area}
                          </span>
                          <span>Leg: {stop.leg_distance_km} km</span>
                          <span>Est. ETA: {stop.estimated_arrival_min} min</span>
                          <span>Payload: {stop.stop_weight_kg} kg</span>
                        </p>
                      </div>

                      {!isDone && (
                        <div className="flex flex-wrap gap-2">
                          {stop.status === 'planned' && (
                            <button
                              type="button"
                              onClick={() => handleQuickStopStatus(stop.id, 'dispatched')}
                              className="inline-flex items-center gap-1.5 rounded-xl bg-sky-600 px-3.5 py-2 text-xs font-semibold text-white hover:bg-sky-700"
                            >
                              <Play className="h-3.5 w-3.5" />
                              Mark Dispatched
                            </button>
                          )}
                          {(stop.status === 'dispatched' || stop.status === 'partially_delivered') && (
                            <button
                              type="button"
                              onClick={() => handleQuickStopStatus(stop.id, 'in_transit')}
                              className="inline-flex items-center gap-1.5 rounded-xl bg-indigo-600 px-3.5 py-2 text-xs font-semibold text-white hover:bg-indigo-700"
                            >
                              <Navigation className="h-3.5 w-3.5" />
                              In Transit
                            </button>
                          )}
                          {stop.status !== 'planned' && (
                            <button
                              type="button"
                              onClick={() => openConfirmModal(stop)}
                              className="inline-flex items-center gap-1.5 rounded-xl bg-emerald-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-emerald-700"
                            >
                              <CheckCircle2 className="h-4 w-4" />
                              Confirm Delivery
                            </button>
                          )}
                        </div>
                      )}
                    </div>

                    {/* Shipment Lines */}
                    <div className="mt-4 overflow-x-auto rounded-xl border border-slate-100 bg-slate-50">
                      <table className="min-w-full text-left text-xs">
                        <thead className="border-b border-slate-200 text-[10px] uppercase text-slate-500">
                          <tr>
                            <th className="px-3 py-2">Medical Supply</th>
                            <th className="px-3 py-2">Planned</th>
                            <th className="px-3 py-2">Delivered</th>
                            <th className="px-3 py-2">Remaining</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                          {(stop.shipment_lines || []).map((ln) => (
                            <tr key={ln.id}>
                              <td className="px-3 py-2 font-semibold text-slate-800">
                                {ln.product_code} — {ln.product_name}
                              </td>
                              <td className="px-3 py-2">
                                {ln.quantity_planned} {ln.unit}
                              </td>
                              <td className="px-3 py-2 font-bold text-emerald-700">
                                {ln.quantity_delivered} {ln.unit}
                              </td>
                              <td className="px-3 py-2 text-slate-600">
                                {ln.quantity_remaining} {ln.unit}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>

                    {stop.notes && (
                      <p className="mt-2 text-xs text-slate-500">Remarks: {stop.notes}</p>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}

      {/* Delivery Confirmation Modal */}
      {confirmStop && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4">
          <div className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-xl">
            <h3 className="text-lg font-bold text-slate-900">
              Confirm Delivery — {confirmStop.hospital_code} ({confirmStop.hospital_name})
            </h3>
            <p className="mt-1 text-xs text-slate-500">
              Enter actual delivered quantities (cannot exceed planned quantities). Partial amounts
              automatically mark this stop as Partially Delivered.
            </p>
            <form onSubmit={handleConfirmSubmit} className="mt-4 space-y-4">
              <div className="space-y-2.5">
                {(confirmStop.shipment_lines || []).map((ln) => (
                  <div
                    key={ln.id}
                    className="flex items-center justify-between gap-3 rounded-xl border border-slate-200 bg-slate-50 p-3"
                  >
                    <div className="text-xs">
                      <p className="font-bold text-slate-900">{ln.product_name}</p>
                      <p className="text-slate-500">
                        Planned: {ln.quantity_planned} {ln.unit}
                      </p>
                    </div>
                    <input
                      type="number"
                      min={0}
                      max={ln.quantity_planned}
                      step="any"
                      required
                      value={confirmItems[ln.id] ?? ln.quantity_planned}
                      onChange={(e) =>
                        setConfirmItems((prev) => ({ ...prev, [ln.id]: e.target.value }))
                      }
                      className="w-28 rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-right text-sm font-bold text-slate-900"
                    />
                  </div>
                ))}
              </div>

              <div>
                <label className="mb-1 block text-xs font-semibold text-slate-700">
                  Handover Remarks / Receiver Name
                </label>
                <textarea
                  rows={2}
                  value={confirmRemarks}
                  onChange={(e) => setConfirmRemarks(e.target.value)}
                  placeholder="e.g., Received & signed by Pharmacy Officer at Gate 2..."
                  className="w-full rounded-xl border border-slate-300 p-2.5 text-sm"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setConfirmStop(null)}
                  className="rounded-xl border border-slate-200 px-4 py-2 text-xs font-semibold text-slate-700"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="rounded-xl bg-emerald-600 px-5 py-2 text-xs font-semibold text-white hover:bg-emerald-700 disabled:opacity-60"
                >
                  {submitting ? 'Recording...' : 'Submit Delivery Confirmation'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
