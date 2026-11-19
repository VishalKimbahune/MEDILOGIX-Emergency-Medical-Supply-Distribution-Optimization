import React, { useEffect, useState } from 'react';
import { Bell, CheckCheck, CheckCircle2, RefreshCw } from 'lucide-react';
import {
  fetchNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from '../services/notificationService';
import { useToast } from '../components/common/ToastContext';

const CATEGORY_COLORS = {
  order: 'bg-sky-100 text-sky-800',
  optimization: 'bg-indigo-100 text-indigo-800',
  dispatch: 'bg-teal-100 text-teal-800',
  delivery: 'bg-emerald-100 text-emerald-800',
  warehouse: 'bg-amber-100 text-amber-800',
  account: 'bg-purple-100 text-purple-800',
  system: 'bg-slate-100 text-slate-700',
};

export default function Notifications() {
  const { showToast } = useToast();
  const [items, setItems] = useState([]);
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    try {
      const data = await fetchNotifications({ unread_only: unreadOnly, limit: 100 });
      setItems(data || []);
    } catch {
      showToast('Failed to load notifications', 'error');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [unreadOnly]);

  async function handleRead(id) {
    try {
      await markNotificationRead(id);
      setItems((prev) => prev.map((n) => (n.id === id ? { ...n, is_read: true } : n)));
    } catch {
      showToast('Could not update notification', 'error');
    }
  }

  async function handleReadAll() {
    try {
      await markAllNotificationsRead();
      setItems((prev) => prev.map((n) => ({ ...n, is_read: true })));
      showToast('All notifications marked as read', 'success');
    } catch {
      showToast('Failed to mark all read', 'error');
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Notifications Center</h1>
          <p className="mt-1 text-sm text-slate-500">
            Role-targeted alerts for order approvals, optimization runs, dispatches, and deliveries.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setUnreadOnly((v) => !v)}
            className={`rounded-lg border px-3 py-2 text-xs font-semibold transition ${
              unreadOnly
                ? 'border-sky-600 bg-sky-50 text-sky-800'
                : 'border-slate-200 bg-white text-slate-700 hover:bg-slate-50'
            }`}
          >
            {unreadOnly ? 'Showing Unread Only' : 'Show Unread Only'}
          </button>
          <button
            type="button"
            onClick={handleReadAll}
            className="inline-flex items-center gap-1.5 rounded-lg bg-teal-600 px-3.5 py-2 text-xs font-semibold text-white hover:bg-teal-700"
          >
            <CheckCheck className="h-4 w-4" />
            Mark All Read
          </button>
          <button
            type="button"
            onClick={load}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Refresh
          </button>
        </div>
      </div>

      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        {loading ? (
          <div className="p-10 text-center text-sm text-slate-500">Loading notifications...</div>
        ) : items.length === 0 ? (
          <div className="p-12 text-center">
            <Bell className="mx-auto h-8 w-8 text-slate-300" />
            <p className="mt-3 text-sm font-semibold text-slate-700">No notifications to display</p>
            <p className="mt-1 text-xs text-slate-500">
              New operational events relevant to your account will appear here.
            </p>
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {items.map((n) => (
              <div
                key={n.id}
                className={`flex flex-wrap items-start justify-between gap-4 p-4 transition ${
                  n.is_read ? 'bg-white' : 'bg-sky-50/40'
                }`}
              >
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span
                      className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${
                        CATEGORY_COLORS[n.category] || CATEGORY_COLORS.system
                      }`}
                    >
                      {n.category}
                    </span>
                    <h3 className="text-sm font-semibold text-slate-900">{n.title}</h3>
                    {!n.is_read && (
                      <span className="rounded-full bg-sky-600 px-2 py-0.5 text-[10px] font-bold text-white">
                        NEW
                      </span>
                    )}
                  </div>
                  <p className="mt-1 text-xs leading-relaxed text-slate-600">{n.message}</p>
                  <p className="mt-1.5 text-[11px] text-slate-400">
                    {n.created_at ? new Date(n.created_at).toLocaleString() : ''}
                  </p>
                </div>
                {!n.is_read && (
                  <button
                    type="button"
                    onClick={() => handleRead(n.id)}
                    className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                  >
                    <CheckCircle2 className="h-3.5 w-3.5 text-teal-600" />
                    Mark Read
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
