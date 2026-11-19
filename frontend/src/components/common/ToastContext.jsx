import React, { createContext, useCallback, useContext, useState } from 'react';
import { AlertCircle, CheckCircle2, Info, X } from 'lucide-react';

const ToastContext = createContext(null);

const TOAST_STYLES = {
  success: {
    container: 'border-emerald-200 bg-emerald-50 text-emerald-900',
    icon: CheckCircle2,
    iconColor: 'text-emerald-600',
  },
  error: {
    container: 'border-red-200 bg-red-50 text-red-900',
    icon: AlertCircle,
    iconColor: 'text-red-600',
  },
  warning: {
    container: 'border-orange-200 bg-orange-50 text-orange-900',
    icon: AlertCircle,
    iconColor: 'text-orange-500',
  },
  info: {
    container: 'border-teal-200 bg-teal-50 text-teal-900',
    icon: Info,
    iconColor: 'text-teal-600',
  },
};

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);

  const removeToast = useCallback((id) => {
    setToasts((prev) => prev.filter((item) => item.id !== id));
  }, []);

  const pushToast = useCallback(
    (type, title, message = '') => {
      const id = `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
      setToasts((prev) => [...prev, { id, type, title, message }]);
      window.setTimeout(() => {
        removeToast(id);
      }, 4500);
    },
    [removeToast]
  );

  const api = {
    success: (title, message) => pushToast('success', title, message),
    error: (title, message) => pushToast('error', title, message),
    warning: (title, message) => pushToast('warning', title, message),
    info: (title, message) => pushToast('info', title, message),
    showToast: (title, type = 'info', message = '') =>
      pushToast(TOAST_STYLES[type] ? type : 'info', title, message),
  };

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="pointer-events-none fixed bottom-5 right-5 z-[60] flex w-full max-w-sm flex-col gap-2.5 px-4 sm:px-0">
        {toasts.map((toast) => {
          const style = TOAST_STYLES[toast.type] || TOAST_STYLES.info;
          const Icon = style.icon;
          return (
            <div
              key={toast.id}
              className={`pointer-events-auto flex items-start gap-3 rounded-xl border p-3.5 shadow-lg ${style.container}`}
              role="status"
            >
              <Icon className={`mt-0.5 h-4 w-4 shrink-0 ${style.iconColor}`} />
              <div className="min-w-0 flex-1 text-xs">
                <p className="font-semibold">{toast.title}</p>
                {toast.message && (
                  <p className="mt-0.5 opacity-90 break-words">{toast.message}</p>
                )}
              </div>
              <button
                type="button"
                onClick={() => removeToast(toast.id)}
                className="rounded p-0.5 opacity-60 hover:opacity-100"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return ctx;
}
