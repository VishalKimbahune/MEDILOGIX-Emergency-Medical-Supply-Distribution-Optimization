import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { CheckCircle2, MapPin, Navigation, RefreshCw, Truck } from 'lucide-react';
import { fetchDeliveryDashboard } from '../../services/deliveryPortalService';
import { useToast } from '../../components/common/ToastContext';

export default function DeliveryDashboard() {
  const { showToast } = useToast();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    try {
      const res = await fetchDeliveryDashboard();
      setData(res);
    } catch {
      showToast('Failed to load driver dashboard', 'error');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  const kpis = data?.kpis || {};
  const vehicles = data?.assigned_vehicles || [];
  const active = data?.active_assignments || [];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <span className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-emerald-700">
            <Truck className="h-4 w-4" />
            Delivery Driver Portal
          </span>
          <h1 className="mt-1 text-2xl font-bold text-slate-900">Active Dispatch Overview</h1>
          <p className="mt-1 text-sm text-slate-500">
            View your assigned Pune OSM routes, update transit status, and confirm hospital
            deliveries.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={load}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
          <Link
            to="/delivery/assignments"
            className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-4 py-2 text-xs font-semibold text-white hover:bg-emerald-700"
          >
            <Navigation className="h-4 w-4" />
            Open Routes &amp; Map
          </Link>
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-xs font-semibold text-slate-500">Assigned Vehicles</p>
          <p className="mt-2 text-2xl font-bold text-slate-900">{vehicles.length}</p>
          <p className="mt-1 truncate text-[11px] text-slate-500">
            {vehicles.map((v) => v.vehicle_code).join(', ') || 'None assigned'}
          </p>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-xs font-semibold text-slate-500">Active Routes</p>
          <p className="mt-2 text-2xl font-bold text-sky-700">{kpis.active_routes ?? 0}</p>
          <p className="mt-1 text-[11px] text-slate-500">
            {kpis.total_routes ?? 0} total assigned
          </p>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-xs font-semibold text-slate-500">Pending Stops</p>
          <p className="mt-2 text-2xl font-bold text-amber-600">{kpis.pending_stops ?? 0}</p>
          <p className="mt-1 text-[11px] text-slate-500">Awaiting delivery confirmation</p>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-xs font-semibold text-slate-500">Completed Stops</p>
          <p className="mt-2 text-2xl font-bold text-emerald-700">{kpis.completed_stops ?? 0}</p>
          <p className="mt-1 text-[11px] text-slate-500">
            Est. distance: {kpis.total_distance_km ?? 0} km
          </p>
        </div>
      </div>

      {/* Active Routes */}
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-bold text-slate-900">Your Current Assigned Routes</h2>
          <Link
            to="/delivery/assignments"
            className="text-xs font-semibold text-sky-700 hover:underline"
          >
            View Route Details &amp; Map &rarr;
          </Link>
        </div>

        {active.length === 0 ? (
          <div className="py-10 text-center">
            <CheckCircle2 className="mx-auto h-8 w-8 text-emerald-500" />
            <p className="mt-2 text-sm font-semibold text-slate-700">No active pending routes</p>
            <p className="mt-1 text-xs text-slate-500">
              When an Administrator generates a dispatch plan for your vehicle, it will appear here.
            </p>
          </div>
        ) : (
          <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
            {active.map((a) => (
              <div
                key={a.id}
                className="rounded-xl border border-slate-200 bg-slate-50/70 p-4"
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-sm font-bold text-navy-900">{a.plan_code}</span>
                  <span className="rounded-full bg-sky-100 px-2.5 py-0.5 text-[10px] font-bold uppercase text-sky-800">
                    {a.status.replace('_', ' ')}
                  </span>
                </div>
                <p className="mt-1 text-xs text-slate-600">
                  Vehicle <strong>{a.vehicle_code}</strong> &bull; From{' '}
                  <strong>{a.warehouse_code}</strong> ({a.warehouse_name})
                </p>
                <div className="mt-3 flex flex-wrap gap-3 text-[11px] text-slate-600">
                  <span className="inline-flex items-center gap-1">
                    <MapPin className="h-3.5 w-3.5 text-teal-600" />
                    {a.stops?.length || 0} hospital stop(s)
                  </span>
                  <span>Est. {a.route_distance_km} km</span>
                  <span>~{a.estimated_duration_min} min (speed profile)</span>
                </div>
                <Link
                  to="/delivery/assignments"
                  className="mt-4 flex w-full items-center justify-center rounded-lg bg-navy-900 px-3 py-2 text-xs font-semibold text-white hover:bg-navy-800"
                >
                  Open Route &amp; Confirm Stops
                </Link>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
