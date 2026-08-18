export function formatNumber(value) {
  if (value === null || value === undefined) return '0';
  return Number(value).toLocaleString();
}

export function formatPercent(value, decimals = 0) {
  if (value === null || value === undefined) return '0%';
  const num = typeof value === 'number' ? value : parseFloat(value);
  if (isNaN(num)) return '0%';
  // If value is between 0 and 1, convert to 0-100%
  const pct = num <= 1.0 && num >= 0 ? num * 100 : num;
  return `${pct.toFixed(decimals)}%`;
}

export function formatDate(value) {
  if (!value) return '—';
  try {
    const d = new Date(value);
    if (isNaN(d.getTime())) return String(value);
    return d.toISOString().split('T')[0];
  } catch {
    return String(value);
  }
}

export function formatScore(score) {
  if (score === null || score === undefined) return 0;
  return Math.round(Number(score) * 100);
}

export function getPriorityTier(score) {
  const s = Number(score || 0);
  if (s >= 0.75) return 'HIGH';
  if (s >= 0.50) return 'MEDIUM';
  return 'LOW';
}

export function getPriorityColor(tierOrScore) {
  const tier = typeof tierOrScore === 'number' ? getPriorityTier(tierOrScore) : String(tierOrScore || '').toUpperCase();
  if (tier === 'HIGH') return { bg: 'bg-error-container/60', text: 'text-error', border: 'border-error/30', accent: 'bg-error' };
  if (tier === 'MEDIUM') return { bg: 'bg-secondary-container/30', text: 'text-secondary', border: 'border-secondary/30', accent: 'bg-secondary' };
  return { bg: 'bg-surface-container-high', text: 'text-outline', border: 'border-outline/20', accent: 'bg-outline' };
}
