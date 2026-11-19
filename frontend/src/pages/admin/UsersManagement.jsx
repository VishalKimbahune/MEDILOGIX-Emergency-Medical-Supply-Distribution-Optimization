import React, { useEffect, useState } from 'react';
import {
  CheckCircle2,
  KeyRound,
  Plus,
  RefreshCw,
  ShieldCheck,
  UserCheck,
  UserX,
  XCircle,
} from 'lucide-react';
import {
  approveUser,
  createUser,
  initiateUserRecovery,
  listUsers,
  rejectUser,
  toggleUserStatus,
} from '../../services/adminService';
import { fetchPublicOrganizations } from '../../services/authService';
import { useToast } from '../../components/common/ToastContext';

const ROLE_BADGE = {
  admin: 'bg-sky-100 text-sky-800',
  hospital: 'bg-teal-100 text-teal-800',
  warehouse: 'bg-amber-100 text-amber-800',
  delivery: 'bg-emerald-100 text-emerald-800',
};

const APPROVAL_BADGE = {
  approved: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  pending: 'bg-amber-50 text-amber-800 border-amber-200',
  rejected: 'bg-red-50 text-red-700 border-red-200',
};

export default function UsersManagement() {
  const { showToast } = useToast();
  const [users, setUsers] = useState([]);
  const [orgs, setOrgs] = useState({ hospitals: [], warehouses: [] });
  const [roleFilter, setRoleFilter] = useState('');
  const [approvalFilter, setApprovalFilter] = useState('');
  const [loading, setLoading] = useState(true);

  // Modals
  const [createOpen, setCreateOpen] = useState(false);
  const [rejectTarget, setRejectTarget] = useState(null);
  const [rejectReason, setRejectReason] = useState('');
  const [recoveryInfo, setRecoveryInfo] = useState(null);

  const [form, setForm] = useState({
    full_name: '',
    email: '',
    password: '',
    phone_number: '',
    role: 'hospital',
    associated_hospital_id: '',
    associated_warehouse_id: '',
  });

  async function load() {
    setLoading(true);
    try {
      const [uList, orgData] = await Promise.all([
        listUsers({
          role: roleFilter || undefined,
          approval_status: approvalFilter || undefined,
        }),
        fetchPublicOrganizations(),
      ]);
      setUsers(uList || []);
      setOrgs(orgData || { hospitals: [], warehouses: [] });
    } catch {
      showToast('Failed to load users', 'error');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [roleFilter, approvalFilter]);

  const pendingCount = users.filter((u) => u.approval_status === 'pending').length;

  async function handleApprove(user) {
    try {
      await approveUser(user.id);
      showToast(`Approved ${user.full_name} (${user.role})`, 'success');
      load();
    } catch (err) {
      showToast(err?.response?.data?.detail || 'Failed to approve user', 'error');
    }
  }

  async function handleRejectSubmit(e) {
    e.preventDefault();
    if (!rejectTarget) return;
    try {
      await rejectUser(rejectTarget.id, rejectReason.trim());
      showToast(`Rejected ${rejectTarget.full_name}`, 'info');
      setRejectTarget(null);
      setRejectReason('');
      load();
    } catch (err) {
      showToast(err?.response?.data?.detail || 'Failed to reject user', 'error');
    }
  }

  async function handleToggleActive(user) {
    try {
      await toggleUserStatus(user.id, !user.is_active);
      showToast(
        `${user.full_name} ${!user.is_active ? 'activated' : 'deactivated'}`,
        'success'
      );
      load();
    } catch (err) {
      showToast(err?.response?.data?.detail || 'Unable to change user status', 'error');
    }
  }

  async function handleInitiateRecovery(user) {
    try {
      const res = await initiateUserRecovery(user.id);
      setRecoveryInfo({ email: user.email, ...res });
      showToast(`Password recovery issued for ${user.email}`, 'success');
    } catch (err) {
      showToast(err?.response?.data?.detail || 'Failed to initiate recovery', 'error');
    }
  }

  async function handleCreateSubmit(e) {
    e.preventDefault();
    try {
      await createUser({
        full_name: form.full_name.trim(),
        email: form.email.trim(),
        password: form.password,
        phone_number: form.phone_number.trim() || null,
        role: form.role,
        associated_hospital_id:
          form.role === 'hospital' ? Number(form.associated_hospital_id) : null,
        associated_warehouse_id:
          form.role === 'warehouse' ? Number(form.associated_warehouse_id) : null,
        is_active: true,
        is_verified: true,
        is_approved: true,
      });
      showToast('User account created successfully', 'success');
      setCreateOpen(false);
      setForm({
        full_name: '',
        email: '',
        password: '',
        phone_number: '',
        role: 'hospital',
        associated_hospital_id: '',
        associated_warehouse_id: '',
      });
      load();
    } catch (err) {
      showToast(err?.response?.data?.detail || 'Failed to create user', 'error');
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Users &amp; Registration Approvals</h1>
          <p className="mt-1 text-sm text-slate-500">
            Review pending institutional accounts, manage role assignments, and enforce governance.
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
            Provision User
          </button>
        </div>
      </div>

      {pendingCount > 0 && (
        <div className="flex items-center justify-between rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs text-amber-900">
          <div className="flex items-center gap-2 font-semibold">
            <ShieldCheck className="h-4 w-4 text-amber-600" />
            <span>
              {pendingCount} account registration(s) awaiting Administrator verification.
            </span>
          </div>
          <button
            type="button"
            onClick={() => setApprovalFilter('pending')}
            className="font-bold text-amber-900 underline"
          >
            Filter Pending
          </button>
        </div>
      )}

      {recoveryInfo && (
        <div className="rounded-xl border border-sky-200 bg-sky-50 p-4 text-xs text-sky-900">
          <div className="flex items-center justify-between">
            <p className="font-semibold">
              Password Recovery Issued for {recoveryInfo.email} ({recoveryInfo.email_delivery_mode})
            </p>
            <button
              type="button"
              onClick={() => setRecoveryInfo(null)}
              className="text-sky-700 underline"
            >
              Dismiss
            </button>
          </div>
          {recoveryInfo.dev_reset_url && (
            <p className="mt-1.5 break-all">
              Dev Reset Link:{' '}
              <a href={recoveryInfo.dev_reset_url} className="font-semibold underline">
                {recoveryInfo.dev_reset_url}
              </a>
            </p>
          )}
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3 rounded-xl border border-slate-200 bg-white p-4">
        <select
          value={roleFilter}
          onChange={(e) => setRoleFilter(e.target.value)}
          className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-700"
        >
          <option value="">All Roles</option>
          <option value="admin">Admin</option>
          <option value="hospital">Hospital</option>
          <option value="warehouse">Warehouse</option>
          <option value="delivery">Delivery</option>
        </select>

        <select
          value={approvalFilter}
          onChange={(e) => setApprovalFilter(e.target.value)}
          className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-700"
        >
          <option value="">All Approval States</option>
          <option value="pending">Pending Approval</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
        </select>
      </div>

      {/* Table */}
      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-left text-xs">
            <thead className="bg-slate-50 font-semibold uppercase tracking-wider text-slate-500">
              <tr>
                <th className="px-4 py-3">User</th>
                <th className="px-4 py-3">Role</th>
                <th className="px-4 py-3">Organization / Fleet</th>
                <th className="px-4 py-3">Approval</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-slate-400">
                    Loading users...
                  </td>
                </tr>
              ) : users.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-slate-400">
                    No matching users found.
                  </td>
                </tr>
              ) : (
                users.map((u) => (
                  <tr key={u.id} className="hover:bg-slate-50/70">
                    <td className="px-4 py-3">
                      <p className="font-semibold text-slate-900">{u.full_name}</p>
                      <p className="text-[11px] text-slate-500">{u.email}</p>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-block rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase ${
                          ROLE_BADGE[u.role] || 'bg-slate-100 text-slate-700'
                        }`}
                      >
                        {u.role}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-600">
                      {u.associated_hospital_code && (
                        <span>
                          {u.associated_hospital_code} — {u.associated_hospital_name}
                        </span>
                      )}
                      {u.associated_warehouse_code && (
                        <span>
                          {u.associated_warehouse_code} — {u.associated_warehouse_name}
                        </span>
                      )}
                      {u.role === 'delivery' && (
                        <span>
                          {u.assigned_vehicle_codes?.length
                            ? u.assigned_vehicle_codes.join(', ')
                            : 'No vehicle assigned'}
                        </span>
                      )}
                      {u.role === 'admin' && <span className="text-slate-400">System-wide</span>}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-block rounded-full border px-2.5 py-0.5 text-[10px] font-bold uppercase ${
                          APPROVAL_BADGE[u.approval_status] || ''
                        }`}
                      >
                        {u.approval_status}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex items-center gap-1 text-[11px] font-semibold ${
                          u.is_active ? 'text-emerald-700' : 'text-red-600'
                        }`}
                      >
                        <span
                          className={`h-1.5 w-1.5 rounded-full ${
                            u.is_active ? 'bg-emerald-500' : 'bg-red-500'
                          }`}
                        />
                        {u.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="inline-flex flex-wrap items-center justify-end gap-1.5">
                        {u.approval_status !== 'approved' && (
                          <button
                            type="button"
                            onClick={() => handleApprove(u)}
                            className="inline-flex items-center gap-1 rounded-lg bg-emerald-600 px-2.5 py-1 text-[11px] font-semibold text-white hover:bg-emerald-700"
                          >
                            <CheckCircle2 className="h-3.5 w-3.5" />
                            Approve
                          </button>
                        )}
                        {u.approval_status === 'pending' && (
                          <button
                            type="button"
                            onClick={() => {
                              setRejectTarget(u);
                              setRejectReason('');
                            }}
                            className="inline-flex items-center gap-1 rounded-lg bg-red-600 px-2.5 py-1 text-[11px] font-semibold text-white hover:bg-red-700"
                          >
                            <XCircle className="h-3.5 w-3.5" />
                            Reject
                          </button>
                        )}
                        <button
                          type="button"
                          onClick={() => handleToggleActive(u)}
                          title={u.is_active ? 'Deactivate Account' : 'Activate Account'}
                          className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2 py-1 text-[11px] font-semibold text-slate-700 hover:bg-slate-50"
                        >
                          {u.is_active ? (
                            <>
                              <UserX className="h-3.5 w-3.5 text-red-600" />
                              Disable
                            </>
                          ) : (
                            <>
                              <UserCheck className="h-3.5 w-3.5 text-emerald-600" />
                              Enable
                            </>
                          )}
                        </button>
                        <button
                          type="button"
                          onClick={() => handleInitiateRecovery(u)}
                          title="Initiate Password Reset"
                          className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2 py-1 text-[11px] font-semibold text-slate-700 hover:bg-slate-50"
                        >
                          <KeyRound className="h-3.5 w-3.5 text-sky-600" />
                          Reset PW
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Reject Modal */}
      {rejectTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
            <h3 className="text-base font-bold text-slate-900">
              Reject Registration — {rejectTarget.full_name}
            </h3>
            <form onSubmit={handleRejectSubmit} className="mt-4 space-y-4">
              <div>
                <label className="mb-1 block text-xs font-semibold text-slate-700">
                  Rejection Reason
                </label>
                <textarea
                  required
                  minLength={3}
                  rows={3}
                  value={rejectReason}
                  onChange={(e) => setRejectReason(e.target.value)}
                  placeholder="Provide a clear reason for audit and communication..."
                  className="w-full rounded-xl border border-slate-300 p-2.5 text-sm focus:border-red-500 focus:outline-none"
                />
              </div>
              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setRejectTarget(null)}
                  className="rounded-lg border border-slate-200 px-4 py-2 text-xs font-semibold text-slate-700"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="rounded-lg bg-red-600 px-4 py-2 text-xs font-semibold text-white hover:bg-red-700"
                >
                  Confirm Rejection
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Provision User Modal */}
      {createOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4">
          <div className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-xl">
            <h3 className="text-lg font-bold text-slate-900">Provision New User Account</h3>
            <form onSubmit={handleCreateSubmit} className="mt-4 space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block text-xs font-semibold text-slate-700">
                    Full Name
                  </label>
                  <input
                    required
                    value={form.full_name}
                    onChange={(e) => setForm({ ...form, full_name: e.target.value })}
                    className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs font-semibold text-slate-700">Role</label>
                  <select
                    value={form.role}
                    onChange={(e) => setForm({ ...form, role: e.target.value })}
                    className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
                  >
                    <option value="admin">Admin</option>
                    <option value="hospital">Hospital</option>
                    <option value="warehouse">Warehouse</option>
                    <option value="delivery">Delivery</option>
                  </select>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block text-xs font-semibold text-slate-700">Email</label>
                  <input
                    type="email"
                    required
                    value={form.email}
                    onChange={(e) => setForm({ ...form, email: e.target.value })}
                    className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs font-semibold text-slate-700">
                    Initial Password
                  </label>
                  <input
                    type="password"
                    required
                    minLength={8}
                    value={form.password}
                    onChange={(e) => setForm({ ...form, password: e.target.value })}
                    className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                  />
                </div>
              </div>
              {form.role === 'hospital' && (
                <div>
                  <label className="mb-1 block text-xs font-semibold text-slate-700">
                    Associated Hospital
                  </label>
                  <select
                    required
                    value={form.associated_hospital_id}
                    onChange={(e) => setForm({ ...form, associated_hospital_id: e.target.value })}
                    className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
                  >
                    <option value="">-- Select Hospital --</option>
                    {orgs.hospitals.map((h) => (
                      <option key={h.id} value={h.id}>
                        {h.code} — {h.name}
                      </option>
                    ))}
                  </select>
                </div>
              )}
              {form.role === 'warehouse' && (
                <div>
                  <label className="mb-1 block text-xs font-semibold text-slate-700">
                    Associated Warehouse
                  </label>
                  <select
                    required
                    value={form.associated_warehouse_id}
                    onChange={(e) => setForm({ ...form, associated_warehouse_id: e.target.value })}
                    className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
                  >
                    <option value="">-- Select Warehouse --</option>
                    {orgs.warehouses.map((w) => (
                      <option key={w.id} value={w.id}>
                        {w.code} — {w.name}
                      </option>
                    ))}
                  </select>
                </div>
              )}
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
                  className="rounded-lg bg-navy-900 px-4 py-2 text-xs font-semibold text-white hover:bg-navy-800"
                >
                  Create Approved User
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
