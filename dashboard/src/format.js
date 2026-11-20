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
  else if (row.role === 'diagnostic') text += ' – diagnostic, unranked';
  else if (row.role === 'control') text += ' – A/A control, unranked';
  return text;
}

export const isMeasured = (row) => row.status === 'measured' || row.status === 'crashed';

const LIMIT_NAMES = { postgresql: 'PostgreSQL-bound', 'load-generator': 'load-generator-bound' };

// What limited a run in how many rounds: PostgreSQL or the load generator (older results: client-bound).
export function clientBound(row, run) {
  const limited = row.flags?.limited_rounds?.[run];
  if (limited) {
    return Object.entries(limited)
      .filter(([, n]) => n)
      .map(([name, n]) => `${LIMIT_NAMES[name] ?? name} ${n}/${row.flags.rounds}`)
      .join(', ');
  }
  const count = row.flags?.client_bound_rounds?.[run] ?? 0;
  return count ? `client-bound ${count}/${row.flags.rounds}` : '';
}

// An absolute median with, in brackets, Axum's median from the same runner.
export function paired(row, path) {
  const text = num(median(row, path));
  const base = row.paired_baseline?.[path];
  if (text === '–' || row.is_baseline || base === undefined || base === null) return text;
  return `${text} (${num(base)})`;
}

// Whether the implementation serves an endpoint (bench.json "endpoints"; older results list none).
export const serves = (row, endpoint) => !row.endpoints || row.endpoints.includes(endpoint);

export const date = (iso) => (iso ? iso.slice(0, 10) : '–');
