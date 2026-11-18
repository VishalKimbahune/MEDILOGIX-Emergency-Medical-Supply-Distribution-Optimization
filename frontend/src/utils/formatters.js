export function formatNumber(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return '—';
  }
  return new Intl.NumberFormat('en-IN').format(Number(value));
}

export function formatCurrencyINR(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return '—';
  }
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 2,
  }).format(Number(value));
}

export function formatPercent(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return '—';
  }
  return `${Number(value).toFixed(1)}%`;
}

export function extractApiError(error, fallback = 'Request failed. Please try again.') {
  const detail = error?.response?.data?.detail;
  if (typeof detail === 'string' && detail.trim()) {
    return detail;
  }
  if (Array.isArray(detail) && detail.length > 0) {
    return detail
      .map((item) => {
        const loc = Array.isArray(item.loc) ? item.loc.slice(1).join('.') : '';
        return loc ? `${loc}: ${item.msg}` : item.msg;
      })
      .join('; ');
  }
  if (error?.message) {
    return error.message;
  }
  return fallback;
}

export function generateNextCode(prefix, existingCodes = [], padLength = 2) {
  let maxNum = 0;
  const regex = new RegExp(`^${prefix}-(\\d+)$`, 'i');
  for (const code of existingCodes) {
    const match = String(code || '').match(regex);
    if (match) {
      maxNum = Math.max(maxNum, parseInt(match[1], 10));
    }
  }
  return `${prefix}-${String(maxNum + 1).padStart(padLength, '0')}`;
}
