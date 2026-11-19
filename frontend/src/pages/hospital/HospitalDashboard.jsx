import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Building2,
  CheckCircle2,
  ClipboardList,
  Clock,
  PackageCheck,
  PlusCircle,
  RefreshCw,
} from 'lucide-react';
import { fetchHospitalDashboard } from '../../services/hospitalPortalService';
import OrderTimeline from '../../components/common/OrderTimeline';
import { useToast } from '../../components/common/ToastContext';

export default function HospitalDashboard() {
  const { showToast } = useToast();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    try {
      const res = await fetchHospitalDashboard();
      setData(res);
    } catch {
      showToast('Failed to load hospital dashboard', 'error');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  const hosp = data?.hospital;
  const kpis = data?.kpis || {};
  const recent = data?.recent_orders || [];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <Building2 className="h-5 w-5 text-teal-600" />
            <span className="text-xs font-bold uppercase tracking-wider text-teal-700">
              {hosp ? `${hosp.code} • ${hosp.area}` : 'Hospital Portal'}
            </span>
          </div>
          <h1 className="mt-1 text-2xl font-bold text-slate-900">
            {hosp?.name || 'Hospital Supply Dashboard'}
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Submit emergency medical supply requests and track real-time allocation &amp; delivery
            progress.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={load}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
          <Link
            to="/hospital/orders/new"
            className="inline-flex items-center gap-1.5 rounded-lg bg-teal-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-teal-700"
          >
            <PlusCircle className="h-4 w-4" />
            New Supply Order
          </Link>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500">Pending Approval</span>
            <Clock className="h-4 w-4 text-amber-500" />
          </div>
          <p className="mt-2 text-2xl font-bold text-slate-900">
            {kpis.pending_approval_orders ?? 0}
          </p>
          <p className="mt-1 text-[11px] text-slate-500">Awaiting Admin review</p>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500">Approved / Active</span>
            <ClipboardList className="h-4 w-4 text-sky-600" />
          </div>
          <p className="mt-2 text-2xl font-bold text-slate-900">
            {kpis.approved_active_orders ?? 0}
          </p>
          <p className="mt-1 text-[11px] text-slate-500">Eligible for OR optimization</p>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500">In-Transit / Dispatched</span>
            <PackageCheck className="h-4 w-4 text-teal-600" />
          </div>
          <p className="mt-2 text-2xl font-bold text-slate-900">
            {kpis.in_transit_orders ?? 0}
          </p>
          <p className="mt-1 text-[11px] text-slate-500">Scheduled on Pune routes</p>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500">Delivered Orders</span>
            <CheckCircle2 className="h-4 w-4 text-emerald-600" />
          </div>
          <p className="mt-2 text-2xl font-bold text-slate-900">
            {kpis.delivered_orders ?? 0}
          </p>
          <p className="mt-1 text-[11px] text-slate-500">
            {kpis.total_delivered_units?.toLocaleString() ?? 0} units confirmed
          </p>
        </div>
      </div>

      {/* Recent Orders with Visual Timeline */}
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-bold text-slate-900">Recent Supply Requests &amp; Tracking</h2>
          <Link
            to="/hospital/orders"
            className="text-xs font-semibold text-sky-700 hover:underline"
          >
            View All Orders
          </Link>
        </div>

        {loading ? (
          <p className="py-8 text-center text-xs text-slate-400">Loading your hospital orders...</p>
        ) : recent.length === 0 ? (
          <div className="py-10 text-center">
            <p className="text-sm font-semibold text-slate-700">No supply orders submitted yet</p>
            <Link
              to="/hospital/orders/new"
              className="mt-3 inline-flex items-center gap-1.5 rounded-lg bg-teal-600 px-4 py-2 text-xs font-semibold text-white"
            >
              <PlusCircle className="h-4 w-4" />
              Create First Order
            </Link>
          </div>
        ) : (
          <div className="mt-4 space-y-4">
            {recent.slice(0, 6).map((ord) => (
              <div
                key={ord.id}
                className="rounded-xl border border-slate-200 bg-slate-50/50 p-4"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-xs font-bold text-navy-900">
                      {ord.demand_code}
                    </span>
                    <span className="text-xs font-semibold text-slate-800">
                      {ord.product_name} ({ord.quantity_requested.toLocaleString()} {ord.unit})
                    </span>
                    <span
                      className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${
                        ord.priority_level === 'critical'
                          ? 'bg-red-100 text-red-800'
                          : ord.priority_level === 'high'
                          ? 'bg-amber-100 text-amber-800'
                          : 'bg-slate-200 text-slate-700'
                      }`}
                    >
                      {ord.priority_level}
                    </span>
                  </div>
                  <div className="text-xs text-slate-500">
                    Allocated: <strong>{ord.allocated_quantity}</strong> &bull; Delivered:{' '}
                    <strong className="text-emerald-700">{ord.delivered_quantity}</strong>
                  </div>
                </div>
                {ord.rejection_reason && (
                  <p className="mt-2 rounded-lg bg-red-50 px-3 py-1.5 text-xs text-red-700">
                    Rejection Reason: {ord.rejection_reason}
                  </p>
                )}
                <OrderTimeline timeline={ord.timeline} />
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
