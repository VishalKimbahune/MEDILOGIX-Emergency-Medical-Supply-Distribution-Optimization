import React from 'react';
import { AlertTriangle, CheckCircle2 } from 'lucide-react';
import Modal from './Modal';

export default function ConfirmDialog({
  open,
  onClose,
  onConfirm,
  title,
  message,
  details,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  tone = 'danger', // danger | warning | primary
  loading = false,
}) {
  const isDanger = tone === 'danger';
  const isWarning = tone === 'warning';

  const confirmClasses = isDanger
    ? 'bg-red-600 hover:bg-red-700 text-white'
    : isWarning
    ? 'bg-orange-500 hover:bg-orange-600 text-white'
    : 'bg-teal-600 hover:bg-teal-700 text-white';

  const iconClasses = isDanger
    ? 'bg-red-50 text-red-600 ring-red-100'
    : isWarning
    ? 'bg-orange-50 text-orange-600 ring-orange-100'
    : 'bg-teal-50 text-teal-600 ring-teal-100';

  return (
    <Modal
      open={open}
      onClose={loading ? undefined : onClose}
      title={title}
      size="sm"
      footer={
        <>
          <button
            type="button"
            disabled={loading}
            onClick={onClose}
            className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50"
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            disabled={loading}
            onClick={onConfirm}
            className={`rounded-lg px-4 py-2 text-xs font-semibold shadow-sm transition disabled:opacity-50 ${confirmClasses}`}
          >
            {loading ? 'Processing...' : confirmLabel}
          </button>
        </>
      }
    >
      <div className="flex items-start gap-3.5">
        <div
          className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full ring-4 ${iconClasses}`}
        >
          {isDanger || isWarning ? (
            <AlertTriangle className="h-5 w-5" />
          ) : (
            <CheckCircle2 className="h-5 w-5" />
          )}
        </div>
        <div className="text-sm text-slate-700">
          <p>{message}</p>
          {details && (
            <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-700">
              {details}
            </div>
          )}
        </div>
      </div>
    </Modal>
  );
}
