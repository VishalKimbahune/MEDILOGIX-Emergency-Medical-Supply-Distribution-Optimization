import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { AlertCircle, CheckCircle2, Mail } from 'lucide-react';
import AuthLayout from './AuthLayout';
import { forgotPassword } from '../../services/authService';

export default function ForgotPassword() {
  const [email, setEmail] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      const data = await forgotPassword(email.trim());
      setResult(data);
    } catch (err) {
      setError(
        err?.response?.data?.detail || 'Unable to process reset request right now. Try again later.'
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthLayout
      title="Password Recovery"
      subtitle="Enter your registered email address to receive a single-use password reset link."
    >
      {error && (
        <div className="mb-4 flex items-start gap-2.5 rounded-xl border border-red-200 bg-red-50 p-3.5 text-xs text-red-800">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-red-600" />
          <span>{error}</span>
        </div>
      )}

      {result ? (
        <div className="space-y-4">
          <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-xs text-emerald-900">
            <div className="flex items-center gap-2 font-semibold">
              <CheckCircle2 className="h-4 w-4 text-emerald-600" />
              <span>Recovery Request Processed</span>
            </div>
            <p className="mt-1.5 leading-relaxed">{result.message}</p>
          </div>

          {result.dev_reset_url && (
            <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-xs text-amber-900">
              <p className="font-semibold">Development Mode Fallback (SMTP Not Configured)</p>
              <p className="mt-1">{result.dev_notice}</p>
              <a
                href={result.dev_reset_url}
                className="mt-2 inline-block font-semibold text-sky-700 underline break-all"
              >
                Open Single-Use Password Reset Page
              </a>
            </div>
          )}

          <Link
            to="/login"
            className="flex w-full items-center justify-center rounded-xl bg-navy-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-navy-800"
          >
            Back to Sign In
          </Link>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-600">
              Email Address
            </label>
            <div className="relative">
              <Mail className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@organization.org"
                className="w-full rounded-xl border border-slate-300 py-2.5 pl-10 pr-3 text-sm focus:border-sky-600 focus:outline-none focus:ring-2 focus:ring-sky-600/20"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-xl bg-navy-900 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-navy-800 disabled:opacity-60"
          >
            {submitting ? 'Issuing Recovery Link...' : 'Send Reset Link'}
          </button>

          <div className="text-center text-sm">
            <Link to="/login" className="font-semibold text-slate-600 hover:text-slate-900">
              Return to Sign In
            </Link>
          </div>
        </form>
      )}
    </AuthLayout>
  );
}
