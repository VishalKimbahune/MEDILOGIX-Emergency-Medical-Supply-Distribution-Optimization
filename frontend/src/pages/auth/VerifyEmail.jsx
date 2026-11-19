import React, { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { AlertCircle, CheckCircle2, Loader2 } from 'lucide-react';
import AuthLayout from './AuthLayout';
import { verifyEmail } from '../../services/authService';

export default function VerifyEmail() {
  const [params] = useSearchParams();
  const token = params.get('token') || '';
  const [status, setStatus] = useState('verifying');
  const [message, setMessage] = useState('');

  useEffect(() => {
    if (!token) {
      setStatus('error');
      setMessage('Missing verification token in link.');
      return;
    }
    verifyEmail(token)
      .then((res) => {
        setStatus('success');
        setMessage(res?.message || 'Email verified successfully.');
      })
      .catch((err) => {
        setStatus('error');
        setMessage(
          err?.response?.data?.detail ||
            'Verification token is invalid, expired, or has already been used.'
        );
      });
  }, [token]);

  return (
    <AuthLayout title="Email Verification" subtitle="Confirming your MEDILOGIX email address.">
      {status === 'verifying' && (
        <div className="flex flex-col items-center py-6 text-slate-600">
          <Loader2 className="h-7 w-7 animate-spin text-teal-600" />
          <p className="mt-3 text-sm font-medium">Verifying token...</p>
        </div>
      )}

      {status === 'success' && (
        <div className="space-y-4">
          <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-xs text-emerald-900">
            <div className="flex items-center gap-2 font-semibold">
              <CheckCircle2 className="h-4 w-4 text-emerald-600" />
              <span>Email Verified</span>
            </div>
            <p className="mt-1">{message}</p>
          </div>
          <Link
            to="/login"
            className="flex w-full items-center justify-center rounded-xl bg-navy-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-navy-800"
          >
            Continue to Sign In
          </Link>
        </div>
      )}

      {status === 'error' && (
        <div className="space-y-4">
          <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-xs text-red-800">
            <div className="flex items-center gap-2 font-semibold">
              <AlertCircle className="h-4 w-4 text-red-600" />
              <span>Verification Failed</span>
            </div>
            <p className="mt-1">{message}</p>
          </div>
          <Link
            to="/login"
            className="flex w-full items-center justify-center rounded-xl bg-navy-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-navy-800"
          >
            Back to Sign In
          </Link>
        </div>
      )}
    </AuthLayout>
  );
}
