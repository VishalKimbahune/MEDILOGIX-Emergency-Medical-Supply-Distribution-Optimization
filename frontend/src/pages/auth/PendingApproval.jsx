import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Clock, CheckCircle2, MailCheck } from 'lucide-react';
import AuthLayout from './AuthLayout';

export default function PendingApproval() {
  const { state } = useLocation();
  const email = state?.email;
  const role = state?.role;
  const devVerifyUrl = state?.devVerifyUrl;

  return (
    <AuthLayout
      title="Registration Submitted"
      subtitle="Your account is awaiting Administrator verification and approval."
    >
      <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
        <div className="flex items-start gap-3">
          <Clock className="mt-0.5 h-5 w-5 shrink-0 text-amber-600" />
          <div className="text-xs leading-relaxed text-amber-900">
            <p className="font-semibold">Pending Administrator Approval</p>
            <p className="mt-1">
              {email ? (
                <>
                  Account <strong>{email}</strong> ({role?.toUpperCase() || 'USER'}) has been
                  created in <strong>pending</strong> state.
                </>
              ) : (
                'Your registration has been received and is pending Administrator review.'
              )}{' '}
              You will be able to sign in once an administrator approves your organization
              association.
            </p>
          </div>
        </div>
      </div>

      {devVerifyUrl && (
        <div className="mt-4 rounded-xl border border-sky-200 bg-sky-50 p-4 text-xs text-sky-900">
          <div className="flex items-center gap-2 font-semibold">
            <MailCheck className="h-4 w-4 text-sky-600" />
            <span>Development Email Verification Link (SMTP Not Configured)</span>
          </div>
          <p className="mt-1 text-sky-800">
            In local development without SMTP configured, you can verify your email address
            directly:
          </p>
          <a
            href={devVerifyUrl}
            className="mt-2 inline-flex items-center gap-1.5 font-semibold text-sky-700 underline break-all"
          >
            <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
            Verify Email Address
          </a>
        </div>
      )}

      <div className="mt-6 flex flex-col gap-2">
        <Link
          to="/login"
          className="flex w-full items-center justify-center rounded-xl bg-navy-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-navy-800"
        >
          Return to Sign In
        </Link>
      </div>
    </AuthLayout>
  );
}
