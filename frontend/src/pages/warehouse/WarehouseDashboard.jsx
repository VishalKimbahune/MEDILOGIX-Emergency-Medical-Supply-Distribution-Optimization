import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  AlertTriangle,
  Boxes,
  PackageCheck,
  RefreshCw,
  ShieldAlert,
  Warehouse,
} from 'lucide-react';
import { fetchWarehouseDashboard } from '../../services/warehousePortalService';
import { useToast } from '../../components/common/ToastContext';

const STATUS_BANNER = {
  active: 'border-emerald-200 bg-emerald-50 text-emerald-900',
  maintenance: 'border-amber-200 bg-amber-50 text-amber-900',
  inactive: 'border-red-200 bg-red-50 text-red-900',
};

export default function WarehouseDashboard() {
  const { showToast } = useToast();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    try {
      const res = await fetchWarehouseDashboard();
      setData(res);
    } catch {
      showToast('Failed to load warehouse dashboard', 'error');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  const wh = data?.warehouse;
  const kpis = data?.kpis || {};
  const lowStock = data?.low_stock_alerts || [];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <Warehouse className="h-5 w-5 text-amber-600" />
            <span className="text-xs font-bold uppercase tracking-wider text-amber-700">
              {wh ? `${wh.code} • ${wh.area}` : 'Warehouse Portal'}
            </span>
          </div>
          <h1 className="mt-1 text-2xl font-bold text-slate-900">
            {wh?.name || 'Warehouse Operations Dashboard'}
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Manage physical inventory, review optimization allocations, and prepare outgoing
            hospital shipments.
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
            to="/warehouse/inventory"
            className="rounded-lg bg-navy-900 px-4 py-2 text-xs font-semibold text-white hover:bg-navy-800"
          >
            Manage Stock
          </Link>
        </div>
      </div>

      {wh && (
        <div
          className={`flex flex-wrap items-center justify-between gap-3 rounded-xl border px-4 py-3 text-xs ${
            STATUS_BANNER[wh.status] || STATUS_BANNER.active
          }`}
        >
          <div className="flex items-center gap-2">
            <ShieldAlert className="h-4 w-4 shrink-0" />
            <span>
              Operational Status: <strong className="uppercase">{wh.status}</strong> —{' '}
              {wh.status === 'active'
                ? 'Eligible for new LP optimization runs and dispatch plans.'
                : 'Excluded from new optimization runs while preserving stock, history, and active dispatches.'}
            </span>
          </div>
          <Link to="/warehouse/profile" className="font-bold underline">
            Change Status
          </Link>
        </div>
      )}

      {/* KPIs */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500">Physical Stock</span>
            <Boxes className="h-4 w-4 text-teal-600" />
          </div>
          <p className="mt-2 text-2xl font-bold text-slate-900">
            {(kpis.total_physical_stock ?? 0).toLocaleString()}
          </p>
          <p className="mt-1 text-[11px] text-slate-500">
            Utilization: {kpis.storage_utilization_pct ?? 0}% of capacity
          </p>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500">Net Available Stock</span>
            <Boxes className="h-4 w-4 text-emerald-600" />
          </div>
          <p className="mt-2 text-2xl font-bold text-emerald-700">
            {(kpis.total_net_available_stock ?? 0).toLocaleString()}
          </p>
          <p className="mt-1 text-[11px] text-slate-500">
            Reserved: {(kpis.total_reserved_stock ?? 0).toLocaleString()} units
          </p>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500">Low-Stock Alerts</span>
            <AlertTriangle className="h-4 w-4 text-amber-500" />
          </div>
          <p className="mt-2 text-2xl font-bold text-slate-900">{lowStock.length}</p>
          <p className="mt-1 text-[11px] text-slate-500">At or below reorder threshold</p>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500">Pending Prep Shipments</span>
            <PackageCheck className="h-4 w-4 text-sky-600" />
          </div>
          <p className="mt-2 text-2xl font-bold text-slate-900">
            {kpis.pending_preparation_shipments ?? 0}
          </p>
          <p className="mt-1 text-[11px] text-slate-500">
            <Link to="/warehouse/shipments" className="font-semibold text-sky-700 hover:underline">
              Open dispatch queue &rarr;
            </Link>
          </p>
        </div>
      </div>

      {/* Low Stock Alerts */}
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-bold text-slate-900">Stock Alerts</h2>
          <Link to="/warehouse/inventory" className="text-xs font-semibold text-sky-700 hover:underline">
            Adjust Inventory
          </Link>
        </div>
        {lowStock.length === 0 ? (
          <p className="mt-4 text-xs text-emerald-700">
            All tracked medical products are comfortably above reorder levels.
          </p>
        ) : (
          <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
            {lowStock.map((item) => (
              <div
                key={item.inventory_id}
                className="flex items-center justify-between rounded-xl border border-amber-200 bg-amber-50 p-3.5 text-xs"
              >
                <div>
                  <p className="font-bold text-amber-950">
                    {item.product_code} — {item.product_name}
                  </p>
                  <p className="mt-0.5 text-amber-800">
                    Available: <strong>{item.quantity_available}</strong> / Reorder:{' '}
                    {item.reorder_level}
                  </p>
                </div>
                <span className="rounded-full bg-amber-200 px-2.5 py-0.5 text-[10px] font-bold uppercase text-amber-950">
                  {item.out_of_stock ? 'OUT OF STOCK' : 'LOW STOCK'}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
