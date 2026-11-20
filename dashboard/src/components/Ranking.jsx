import { useState } from 'react';
import { label, num } from '../format';

// Renders `rankings` from latest.json (computed by bench/rankings.py; see the
// README's schema section). Every score is oriented so that higher is better
// and Axum, the reference, is 1.00; this component computes nothing.

const times = (value) => {
  if (value === null || value === undefined) return '–';
  return `${value.toFixed(value >= 0.1 ? 2 : 3)}×`;
};

function position(entry) {
  if (entry.status === 'reference') return 'ref.';
  if (entry.status === 'diagnostic') return 'diag.';
  if (entry.status === 'A/A control') return 'A/A';
  if (entry.position === null || entry.position === undefined) return '–';
  return entry.tie ? `${entry.position}=` : String(entry.position);
}

const RUN_NAMES = {
  'tier1.text': '/text',
  'tier1.json': '/json',
  'tier1.db-single': '/db-single',
  'tier1.html': '/html',
  'tier1.queries': '/queries',
  'tier1.updates': '/updates',
  'tier1.fortunes': '/fortunes',
  'tier1.world': 'GET /world/{id}',
  'tier1.worlds': 'GET /worlds',
  'tier1.world-update': 'PUT /world/{id}',
  'tier1.form': 'POST /form',
  'tier1.me': 'GET /me',
  tier2: 'Tier 2',
  tier4: 'Tier 4',
};

const LIMITS = { postgresql: 'PostgreSQL-bound', 'load-generator': 'load-generator-bound' };

function notes(entry, names) {
  if (['not measured', 'incomplete', 'not comparable', 'errors', 'unstable'].includes(entry.status)) return entry.reason;
  const out = [];
  if (entry.role_note && ['diagnostic', 'A/A control'].includes(entry.status)) out.push(entry.role_note);
  if (entry.within_reference_margin) out.push('within the tie margin of Axum');
  if (entry.status !== 'reference' && entry.spread?.effective_percent !== null && entry.spread?.effective_percent !== undefined) {
    const cpus = entry.spread.cpu_models?.length ? ` over ${entry.spread.cpu_models.join(', ')}` : '';
    out.push(`spread between jobs ±${entry.spread.effective_percent.toFixed(1)}%${cpus}`);
  }
  if (entry.tie && entry.tied_with?.length) out.push(`tie with ${entry.tied_with.map(names).join(', ')}`);
  const limited = Object.entries(entry.limited_runs ?? {}).map(
    ([run, counts]) =>
      `${RUN_NAMES[run] ?? run}: ${Object.entries(counts)
        .map(([name, n]) => `${LIMITS[name] ?? name} ${n}`)
        .join(', ')}`,
  );
  if (limited.length) out.push(limited.join('; '));
  if (entry.efficiency_runs?.length) {
    out.push(`scored by CPU efficiency on ${entry.efficiency_runs.map((r) => RUN_NAMES[r] ?? r).join(', ')}`);
  }
  return out.join('; ');
}

function Bar({ value, scale }) {
  if (value === null || value === undefined) return null;
  return (
    <span className="bar" aria-hidden="true">
      <span className="bar-fill" style={{ width: `${Math.min(value / scale, 1) * 100}%` }} />
      <span className="bar-axum" style={{ left: `${(1 / scale) * 100}%` }} />
    </span>
  );
}

// The measured value shown next to the score, and the extra columns, per category.
// Throughput scores come from capacity ratios ("*": CPU efficiency decided at least one run).
const score = (e) => `${times(e.score ?? e.ratio)}${e.efficiency_runs?.length ? '*' : ''}`;

const capacity = (e, ep) => {
  const rate = e.detail?.error_rates?.[ep];
  if (rate > 0.01) return `${(rate * 100).toFixed(1)}% errors`;
  const value = e.detail?.capacity?.[ep] ?? e.detail?.rps_ratio?.[ep];
  return `${times(value)}${e.detail?.basis?.[ep] === 'cpu' ? '*' : ''}`;
};
const pgCost = (e, ep) => {
  const own = e.detail?.db_us_per_request?.[ep];
  const ratio = e.detail?.db_us_ratio?.[ep];
  if (own === null || own === undefined) return '–';
  return `${num(own)} µs${ratio === null || ratio === undefined ? '' : ` (${times(ratio)})`}`;
};
const throughput = (endpoints, labels, database = []) => ({
  title: 'Score',
  value: score,
  columns: [...labels, ...database.map((ep) => `PG µs/req /${ep}`)],
  cells: (e) => [...endpoints.map((ep) => capacity(e, ep)), ...database.map((ep) => pgCost(e, ep))],
});

const DETAIL = {
  hello: throughput(['text', 'json', 'html'], ['/text', '/json', '/html']),
  database: throughput(
    ['db-single', 'queries', 'updates', 'fortunes'],
    ['/db-single', '/queries', '/updates', '/fortunes'],
    ['db-single', 'queries', 'updates', 'fortunes'],
  ),
  application: {
    ...throughput(
      ['world', 'worlds', 'world-update', 'form', 'me'],
      ['GET /world/{id}', 'GET /worlds', 'PUT /world/{id}', 'POST /form', 'GET /me'],
    ),
    columns: ['GET /world/{id}', 'GET /worlds', 'PUT /world/{id}', 'POST /form', 'GET /me', 'CSRF', 'Session store'],
    cells: (e) => [
      ...['world', 'worlds', 'world-update', 'form', 'me'].map((ep) => capacity(e, ep)),
      e.detail?.csrf ?? '–',
      e.detail?.session_store ?? '–',
    ],
  },
  memory: {
    title: 'Score',
    value: (e) => times(e.score),
    columns: ['High-water mark (MiB)', 'Axum, same runners (MiB)'],
    cells: (e) => [num(e.detail?.value, 1), num(e.detail?.reference, 1)],
  },
  startup: {
    title: 'Score',
    value: (e) => times(e.score),
    columns: ['Start-up (s)', 'Axum, same runners (s)'],
    cells: (e) => [num(e.detail?.value, 2), num(e.detail?.reference, 2)],
  },
};

const worst = (tier) => {
  const rate = tier?.error_rate_max;
  if (rate === null || rate === undefined) return '–';
  return rate ? `${(rate * 100).toFixed(2)}%` : '0';
};

function StabilityTable({ stability, names }) {
  return (
    <div className="table-wrap">
      <table className="ranking">
        <caption>{`${stability.title} (${stability.tier}): ${stability.description}.`}</caption>
        <thead>
          <tr>
            <th className="text" scope="col">Implementation</th>
            <th className="text" scope="col">Result</th>
            <th scope="col">Tier 2 req/s</th>
            <th scope="col">Tier 2 worst errors</th>
            <th scope="col">Tier 4 req/s</th>
            <th scope="col">Tier 4 worst errors</th>
            <th className="text" scope="col">Notes</th>
          </tr>
        </thead>
        <tbody>
          {stability.entries.map((entry) => (
            <tr key={entry.slug} className={entry.status === 'reference' ? 'baseline' : undefined}>
              <th scope="row" className="text">{names(entry.slug, entry)}</th>
              <td className="text">{entry.result ?? '–'}</td>
              <td>{num(entry.detail?.tier2?.rps)}</td>
              <td>{worst(entry.detail?.tier2)}</td>
              <td>{num(entry.detail?.tier4?.rps)}</td>
              <td>{worst(entry.detail?.tier4)}</td>
              <td className="text">{(entry.reasons ?? []).join('; ')}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function RankTable({ caption, title, entries, extra, value, cells, score, names }) {
  const scale = Math.max(1, ...entries.map(score).filter((v) => v !== null && v !== undefined));
  return (
    <div className="table-wrap">
      <table className="ranking">
        <caption>{caption}</caption>
        <thead>
          <tr>
            <th scope="col">#</th>
            <th className="text" scope="col">Implementation</th>
            <th className="text" scope="col">{title}</th>
            {extra.map((title) => (
              <th key={title} scope="col">{title}</th>
            ))}
            <th className="text" scope="col">Notes</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((entry) => (
            <tr key={entry.slug} className={entry.status === 'reference' ? 'baseline' : undefined}>
              <td>{position(entry)}</td>
              <th scope="row" className="text">{names(entry.slug, entry)}</th>
              <td className="text">
                <span className="bar-cell">
                  <span className="bar-value">{value(entry)}</span>
                  <Bar value={score(entry)} scale={scale} />
                </span>
              </td>
              {cells(entry).map((cell, index) => (
                <td key={index}>{cell}</td>
              ))}
              <td className="text">{notes(entry, (slug) => names(slug))}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const margin = (category) => {
  const percent = category.tie_rule?.aa_percent ?? category.tie_margin?.percent;
  const floor = category.tie_rule?.floor_percent;
  const aa = percent === null || percent === undefined ? 'no A/A margin' : `A/A margin ±${percent.toFixed(1)}%`;
  const pooled = floor === null || floor === undefined ? '' : `, pooled floor ±${floor.toFixed(1)}%`;
  return ` Two scores tie when their gap is within the largest of the A/A margin, the root of the sum of squares of their spreads between jobs and the pooled floor (${aa}${pooled}); "≈" rows are within it of Axum.`;
};

export function Ranking({ rankings, rows }) {
  const hasOverall = Boolean(rankings?.overall?.entries);
  const [selected, setSelected] = useState(hasOverall ? 'overall' : (rankings?.categories?.[0]?.key ?? 'overall'));
  if (!rankings?.categories) return <p className="note">These results have no rankings.</p>;
  const byslug = Object.fromEntries(rows.map((r) => [r.slug, r]));
  const names = (slug, entry) => (byslug[slug] ? label(byslug[slug]) : (entry?.framework ?? slug));
  const categories = rankings.categories;
  const cellsOf = Object.fromEntries(categories.map((c) => [c.key, Object.fromEntries(c.entries.map((e) => [e.slug, e]))]));
  const tabs = [
    ...(hasOverall ? [{ key: 'overall', title: 'Overall' }] : []),
    ...categories.map((c) => ({ key: c.key, title: c.title })),
    ...(rankings.stability ? [{ key: 'stability', title: rankings.stability.title }] : []),
  ];
  const category = categories.find((c) => c.key === selected);
  const throughputKinds = ['hello', 'database', 'application', 'speed', 'pressure', 'endurance'];

  return (
    <>
      <div className="tabs" role="group" aria-label="Ranking category">
        {tabs.map((tab) => (
          <button key={tab.key} type="button" aria-pressed={selected === tab.key} onClick={() => setSelected(tab.key)}>
            {tab.title}
          </button>
        ))}
      </div>
      {selected === 'stability' && rankings.stability ? (
        <StabilityTable stability={rankings.stability} names={names} />
      ) : category ? (
        <RankTable
          caption={`${category.title}${category.tier ? ` (${category.tier})` : ''}: ${category.description}. The bar shows the score (longer is better); the line marks Axum.${throughputKinds.includes(category.key) ? ' Endpoint columns are capacity ratios; "*" marks a run scored by requests per CPU-second of the server and PostgreSQL because a side was client-bound.' : ''}${margin(category)}`}
          title={DETAIL[category.key]?.title ?? 'vs Axum'}
          entries={category.entries}
          extra={DETAIL[category.key]?.columns ?? []}
          value={DETAIL[category.key]?.value ?? ((e) => times(e.ratio))}
          cells={DETAIL[category.key]?.cells ?? (() => [])}
          score={(e) => e.score}
          names={names}
        />
      ) : hasOverall ? (
        <RankTable
          caption={`Overall: geometric mean of the ${categories.length} category scores, equal weights. Category columns: position · score (higher is better). The line marks Axum (1.00).`}
          title="Score"
          entries={rankings.overall.entries}
          extra={categories.map((c) => c.title)}
          value={(e) => (e.score === null ? '–' : times(e.score).slice(0, -1))}
          cells={(e) =>
            categories.map((c) => {
              const cell = cellsOf[c.key][e.slug];
              if (!cell || cell.status === 'not measured') return '–';
              return cell.score === null ? cell.status : `${position(cell)} · ${times(cell.score).slice(0, -1)}`;
            })
          }
          score={(e) => e.score}
          names={names}
        />
      ) : null}
    </>
  );
}
