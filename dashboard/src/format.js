// Number formatting and metric lookups shared by the dashboard components.

export const metric = (row, path, kind = 'metrics') => row?.[kind]?.[path] ?? null;

export const median = (row, path, kind = 'metrics') => metric(row, path, kind)?.median ?? null;

export function num(value, digits = 0) {
  if (value === null || value === undefined) return '–';
  return value.toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

export function ratio(row, path) {
  if (row.is_baseline) return metric(row, path) ? '1.00' : '–';
  const value = median(row, path, 'ratios');
  return value === null ? '–' : value.toFixed(2);
}

export function range(row, path, digits = 0) {
  const stat = metric(row, path);
  if (!stat) return '–';
  if (stat.n < 2) return num(stat.median, digits);
  return `${num(stat.median, digits)} (${num(stat.min, digits)}–${num(stat.max, digits)})`;
}

export function errorRate(row, path) {
  const value = median(row, path);
  if (value === null) return '–';
  return value === 0 ? '0' : `${(value * 100).toFixed(2)}%`;
}

export function label(row) {
  let text = row.name;
  if (row.variant) text += ` (${row.variant})`;
  if (row.is_baseline) text += ' – baseline';
  return text;
}

export const isMeasured = (row) => row.status === 'measured' || row.status === 'crashed';

export function clientBound(row, run) {
  const count = row.flags?.client_bound_rounds?.[run] ?? 0;
  return count ? `client-bound ${count}/${row.flags.rounds}` : '';
}

export const date = (iso) => (iso ? iso.slice(0, 10) : '–');
