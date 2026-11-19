import React, { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { AlertCircle, CheckCircle2, Lock } from 'lucide-react';
import AuthLayout from './AuthLayout';
import { resetPassword } from '../../services/authService';

export default function ResetPassword() {
  const [params] = useSearchParams();
  const [token, setToken] = useState(params.get('token') || '');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    if (newPassword !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }
    setSubmitting(true);
    try {
      const res = await resetPassword({
        token: token.trim(),
        new_password: newPassword,
        confirm_password: confirmPassword,
      });
      setSuccess(res?.message || 'Password updated successfully.');
    } catch (err) {
      setError(
        err?.response?.data?.detail ||
          'Reset token is invalid, expired, or has already been used.'
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthLayout
      title="Set New Password"
      subtitle="Choose a strong password. Existing active sessions will be revoked."
    >
      {error && (
        <div className="mb-4 flex items-start gap-2.5 rounded-xl border border-red-200 bg-red-50 p-3.5 text-xs text-red-800">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-red-600" />
          <span>{error}</span>
        </div>
      )}

      {success ? (
        <div className="space-y-4">
          <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-xs text-emerald-900">
            <div className="flex items-center gap-2 font-semibold">
              <CheckCircle2 className="h-4 w-4 text-emerald-600" />
              <span>Password Updated</span>
            </div>
            <p className="mt-1">{success}</p>
          </div>
          <Link
            to="/login"
            className="flex w-full items-center justify-center rounded-xl bg-navy-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-navy-800"
          >
            Sign In Now
          </Link>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-4">
          {!params.get('token') && (
            <div>
              <label className="mb-1 block text-xs font-semibold text-slate-700">Reset Token</label>
              <input
                type="text"
                required
                value={token}
                onChange={(e) => setToken(e.target.value)}
                placeholder="Paste reset token"
                className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm focus:border-sky-600 focus:outline-none"
              />
            </div>
          )}

          <div>
            <label className="mb-1 block text-xs font-semibold text-slate-700">New Password</label>
            <div className="relative">
              <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                type="password"
                required
                minLength={8}
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="Minimum 8 characters"
                className="w-full rounded-xl border border-slate-300 py-2.5 pl-10 pr-3 text-sm focus:border-sky-600 focus:outline-none"
              />
            </div>
          </div>

          <div>
            <label className="mb-1 block text-xs font-semibold text-slate-700">
              Confirm New Password
            </label>
            <input
              type="password"
              required
              minLength={8}
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="Repeat new password"
              className="w-full rounded-xl border border-slate-300 px-3 py-2.5 text-sm focus:border-sky-600 focus:outline-none"
            />
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-xl bg-teal-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-teal-700 disabled:opacity-60"
          >
            {submitting ? 'Updating Password...' : 'Reset Password'}
          </button>
        </form>
      )}
    </AuthLayout>
  );
}
