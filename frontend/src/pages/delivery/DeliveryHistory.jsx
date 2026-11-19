import React, { useEffect, useState } from 'react';
import { CheckCircle2, History } from 'lucide-react';
import { fetchDeliveryAssignments } from '../../services/deliveryPortalService';
import { useToast } from '../../components/common/ToastContext';

export default function DeliveryHistory() {
  const { showToast } = useToast();
  const [completed, setCompleted] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDeliveryAssignments()
      .then((list) => {
        const done = (list || []).filter(
          (a) => a.status === 'delivered' || a.status === 'cancelled'
        );
        setCompleted(done);
      })
      .catch(() => showToast('Failed to load delivery history', 'error'))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Completed Delivery History</h1>
        <p className="mt-1 text-sm text-slate-500">
          Archive of your finished hospital deliveries and confirmed shipment quantities.
        </p>
      </div>

      {loading ? (
        <div className="rounded-2xl border border-slate-200 bg-white p-10 text-center text-sm text-slate-400">
          Loading delivery history...
        </div>
      ) : completed.length === 0 ? (
        <div className="rounded-2xl border border-slate-200 bg-white p-12 text-center">
          <History className="mx-auto h-8 w-8 text-slate-300" />
          <p className="mt-3 text-sm font-semibold text-slate-700">No completed routes yet</p>
          <p className="mt-1 text-xs text-slate-500">
            Completed routes will appear here once all stops are confirmed delivered.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {completed.map((a) => (
            <div
              key={a.id}
              className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                  <span className="font-mono text-sm font-bold text-navy-900">{a.plan_code}</span>
                  <span className="text-xs text-slate-600">
                    {a.vehicle_code} &bull; {a.warehouse_code}
                  </span>
                </div>
                <span className="rounded-full bg-emerald-100 px-2.5 py-0.5 text-[10px] font-bold uppercase text-emerald-800">
                  {a.status}
                </span>
              </div>
              <p className="mt-2 text-xs text-slate-500">
                {a.stops?.length || 0} stops &bull; {a.route_distance_km} km &bull;{' '}
                {a.total_load_kg} kg
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
