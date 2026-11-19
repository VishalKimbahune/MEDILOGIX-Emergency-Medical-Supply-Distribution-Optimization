import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { PlusCircle, RefreshCw } from 'lucide-react';
import { fetchHospitalOrders } from '../../services/hospitalPortalService';
import OrderTimeline from '../../components/common/OrderTimeline';
import { useToast } from '../../components/common/ToastContext';

const STATUS_STYLE = {
  pending_approval: 'bg-amber-100 text-amber-800',
  open: 'bg-sky-100 text-sky-800',
  partially_fulfilled: 'bg-indigo-100 text-indigo-800',
  fulfilled: 'bg-emerald-100 text-emerald-800',
  rejected: 'bg-red-100 text-red-800',
  cancelled: 'bg-slate-200 text-slate-700',
};

export default function HospitalOrders() {
  const { showToast } = useToast();
  const [orders, setOrders] = useState([]);
  const [statusFilter, setStatusFilter] = useState('');
  const [priorityFilter, setPriorityFilter] = useState('');
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    try {
      const list = await fetchHospitalOrders({
        status: statusFilter || undefined,
        priority_level: priorityFilter || undefined,
      });
      setOrders(list || []);
    } catch {
      showToast('Failed to load hospital orders', 'error');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [statusFilter, priorityFilter]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Orders &amp; Delivery Tracking</h1>
          <p className="mt-1 text-sm text-slate-500">
            Track every order from submission through Admin approval, OR allocation, dispatch, and
            confirmed hospital delivery.
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
            className="inline-flex items-center gap-1.5 rounded-lg bg-teal-600 px-4 py-2 text-xs font-semibold text-white hover:bg-teal-700"
          >
            <PlusCircle className="h-4 w-4" />
            Create Order
          </Link>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3 rounded-xl border border-slate-200 bg-white p-4">
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-700"
        >
          <option value="">All Statuses</option>
          <option value="pending_approval">Pending Approval</option>
          <option value="open">Approved / Open</option>
          <option value="partially_fulfilled">Partially Fulfilled</option>
          <option value="fulfilled">Fulfilled</option>
          <option value="rejected">Rejected</option>
          <option value="cancelled">Cancelled</option>
        </select>
        <select
          value={priorityFilter}
          onChange={(e) => setPriorityFilter(e.target.value)}
          className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-700"
        >
          <option value="">All Priorities</option>
          <option value="critical">Critical</option>
          <option value="high">High</option>
          <option value="normal">Normal</option>
        </select>
      </div>

      {loading ? (
        <div className="rounded-2xl border border-slate-200 bg-white p-10 text-center text-sm text-slate-400">
          Loading orders...
        </div>
      ) : orders.length === 0 ? (
        <div className="rounded-2xl border border-slate-200 bg-white p-12 text-center text-sm text-slate-500">
          No orders match your current filters.
        </div>
      ) : (
        <div className="space-y-4">
          {orders.map((ord) => (
            <div
              key={ord.id}
              className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-sm font-bold text-navy-900">
                      {ord.demand_code}
                    </span>
                    {ord.order_group_code && (
                      <span className="rounded bg-slate-100 px-2 py-0.5 font-mono text-[10px] text-slate-600">
                        Group: {ord.order_group_code}
                      </span>
                    )}
                    <span
                      className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase ${
                        STATUS_STYLE[ord.status] || 'bg-slate-100 text-slate-700'
                      }`}
                    >
                      {ord.status.replace('_', ' ')}
                    </span>
                    <span
                      className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase ${
                        ord.priority_level === 'critical'
                          ? 'bg-red-100 text-red-800'
                          : ord.priority_level === 'high'
                          ? 'bg-amber-100 text-amber-800'
                          : 'bg-slate-100 text-slate-700'
                      }`}
                    >
                      {ord.priority_level}
                    </span>
                  </div>
                  <p className="mt-1.5 text-sm font-semibold text-slate-900">
                    {ord.product_name} ({ord.product_code}) —{' '}
                    <span className="text-teal-700">
                      {ord.quantity_requested.toLocaleString()} {ord.unit}
                    </span>
                  </p>
                  {ord.emergency_reason && (
                    <p className="mt-1 text-xs text-slate-600">
                      Justification: {ord.emergency_reason}
                    </p>
                  )}
                  {ord.rejection_reason && (
                    <p className="mt-2 rounded-lg border border-red-200 bg-red-50 px-3 py-1.5 text-xs text-red-800">
                      <strong>Rejected:</strong> {ord.rejection_reason}
                    </p>
                  )}
                </div>

                <div className="grid grid-cols-3 gap-3 rounded-xl border border-slate-100 bg-slate-50 px-4 py-2.5 text-center text-xs">
                  <div>
                    <p className="text-[10px] uppercase text-slate-400">Allocated</p>
                    <p className="font-bold text-slate-800">{ord.allocated_quantity}</p>
                  </div>
                  <div>
                    <p className="text-[10px] uppercase text-slate-400">Delivered</p>
                    <p className="font-bold text-emerald-700">{ord.delivered_quantity}</p>
                  </div>
                  <div>
                    <p className="text-[10px] uppercase text-slate-400">Dispatch</p>
                    <p className="font-mono text-[11px] font-semibold text-sky-700">
                      {ord.dispatch_plan_code || '—'}
                    </p>
                  </div>
                </div>
              </div>

              <OrderTimeline timeline={ord.timeline} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
