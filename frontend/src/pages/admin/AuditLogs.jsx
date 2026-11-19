import React, { useEffect, useState } from 'react';
import { FileClock, RefreshCw, Shield } from 'lucide-react';
import { listAuditLogs } from '../../services/adminService';
import { useToast } from '../../components/common/ToastContext';

export default function AuditLogs() {
  const { showToast } = useToast();
  const [logs, setLogs] = useState([]);
  const [actionFilter, setActionFilter] = useState('');
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    try {
      const data = await listAuditLogs({
        action: actionFilter.trim() || undefined,
        limit: 150,
      });
      setLogs(data || []);
    } catch {
      showToast('Failed to load audit logs', 'error');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Security &amp; Operations Audit Logs</h1>
          <p className="mt-1 text-sm text-slate-500">
            Append-only governance trail across authentication, approvals, optimization runs,
            warehouse movements, and deliveries. Secrets and passwords are never stored.
          </p>
        </div>
        <button
          type="button"
          onClick={load}
          className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Refresh
        </button>
      </div>

      <div className="flex flex-wrap items-center gap-2 rounded-xl border border-slate-200 bg-white p-4">
        <input
          type="text"
          value={actionFilter}
          onChange={(e) => setActionFilter(e.target.value)}
          placeholder="Filter by action (e.g. admin.order_approved, delivery, auth.login)..."
          className="flex-1 min-w-[220px] rounded-lg border border-slate-200 px-3 py-1.5 text-xs focus:border-sky-600 focus:outline-none"
        />
        <button
          type="button"
          onClick={load}
          className="rounded-lg bg-navy-900 px-4 py-1.5 text-xs font-semibold text-white hover:bg-navy-800"
        >
          Apply Filter
        </button>
      </div>

      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-left text-xs">
            <thead className="bg-slate-50 font-semibold uppercase tracking-wider text-slate-500">
              <tr>
                <th className="px-4 py-3">Timestamp</th>
                <th className="px-4 py-3">Actor</th>
                <th className="px-4 py-3">Action</th>
                <th className="px-4 py-3">Target</th>
                <th className="px-4 py-3">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-slate-400">
                    Loading audit trail...
                  </td>
                </tr>
              ) : logs.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-slate-400">
                    <FileClock className="mx-auto mb-2 h-6 w-6 text-slate-300" />
                    No audit records match your filter.
                  </td>
                </tr>
              ) : (
                logs.map((lg) => (
                  <tr key={lg.id} className="hover:bg-slate-50/70">
                    <td className="whitespace-nowrap px-4 py-2.5 text-[11px] text-slate-500">
                      {lg.created_at ? new Date(lg.created_at).toLocaleString() : ''}
                    </td>
                    <td className="px-4 py-2.5">
                      <p className="font-semibold text-slate-800">{lg.actor_email || 'System'}</p>
                      <span className="inline-flex items-center gap-1 text-[10px] uppercase text-slate-400">
                        <Shield className="h-3 w-3" />
                        {lg.actor_role || 'system'}
                      </span>
                    </td>
                    <td className="px-4 py-2.5">
                      <span className="rounded bg-slate-100 px-2 py-0.5 font-mono text-[11px] font-semibold text-navy-900">
                        {lg.action}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-slate-600">
                      {lg.target_entity}
                      {lg.target_id ? ` #${lg.target_id}` : ''}
                    </td>
                    <td className="max-w-xs truncate px-4 py-2.5 font-mono text-[11px] text-slate-500">
                      {lg.metadata_json && Object.keys(lg.metadata_json).length > 0
                        ? JSON.stringify(lg.metadata_json)
                        : '—'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
