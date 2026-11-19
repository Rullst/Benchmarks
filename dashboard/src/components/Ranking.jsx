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
  if (entry.position === null) return '–';
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
  tier2: 'Tier 2',
  tier4: 'Tier 4',
};

function notes(entry, names) {
  if (['not measured', 'incomplete', 'not comparable'].includes(entry.status)) return entry.reason;
  const out = [];
  if (entry.tie && entry.tied_with?.length) out.push(`tie with ${entry.tied_with.map(names).join(', ')}`);
  if (entry.client_bound) out.push('client-bound');
  else if (entry.client_bound_runs?.length && RUN_NAMES[entry.client_bound_runs[0]]) {
    out.push(`client-bound on ${entry.client_bound_runs.map((r) => RUN_NAMES[r] ?? r).join(', ')}`);
  }
  if (entry.efficiency_runs?.length) {
    out.push(`scored by efficiency on ${entry.efficiency_runs.map((r) => RUN_NAMES[r] ?? r).join(', ')}`);
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

function errors(d) {
  const out = [];
  if (d.error_rate) out.push(`errors ${(d.error_rate * 100).toFixed(2)}%`);
  if (d.timeouts) out.push(`${num(d.timeouts)} timeouts`);
  if (d.ram_growing_rounds) out.push(`RAM growing ${d.ram_growing_rounds}/${d.rounds}`);
  if (d.crashed_rounds) out.push(`stopped ${d.crashed_rounds}/${d.rounds}`);
  return out.length ? out.join(', ') : 'none';
}

// The measured value shown next to the score, and the extra columns, per category.
// Throughput scores come from capacity ratios ("*": efficiency decided at least one run).
const score = (e) => `${times(e.score ?? e.ratio)}${e.efficiency_runs?.length ? '*' : ''}`;

const DETAIL = {
  speed: {
    title: 'Score',
    value: score,
    columns: ['/text', '/json', '/db-single', '/html'],
    cells: (e) => ['text', 'json', 'db-single', 'html'].map((ep) => times(e.detail[ep])),
  },
  database: {
    title: 'Score',
    value: score,
    columns: ['/queries', '/updates', '/fortunes'],
    cells: (e) => ['queries', 'updates', 'fortunes'].map((ep) => times(e.detail[ep])),
  },
  pressure: {
    title: 'Score',
    value: score,
    columns: ['req/s', 'p99 (ms)', 'p99 vs Axum'],
    cells: (e) => [num(e.detail.rps), num(e.detail.p99_ms, 2), e.status === 'reference' ? '1.00×' : times(e.detail.p99_ratio)],
  },
  memory: {
    title: 'Peak RAM vs Axum',
    value: (e) => `${times(e.ratio)} RAM`,
    columns: ['Peak RAM (MiB)'],
    cells: (e) => [num(e.detail.peak_ram_mib, 1)],
  },
  endurance: {
    title: 'Score',
    value: score,
    columns: ['req/s', 'Errors, timeouts, RAM growth, stops'],
    cells: (e) => [num(e.detail.rps), e.status === 'not measured' ? '–' : errors(e.detail)],
  },
  startup: {
    title: 'Start-up time',
    value: (e) => (e.detail.startup_s === null || e.detail.startup_s === undefined ? '–' : `${num(e.detail.startup_s, 2)} s`),
    columns: [],
    cells: () => [],
  },
};

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

export function Ranking({ rankings, rows }) {
  const [selected, setSelected] = useState('overall');
  if (!rankings?.categories) return <p className="note">These results have no rankings.</p>;
  const byslug = Object.fromEntries(rows.map((r) => [r.slug, r]));
  const names = (slug, entry) => (byslug[slug] ? label(byslug[slug]) : (entry?.framework ?? slug));
  const categories = rankings.categories;
  const cellsOf = Object.fromEntries(categories.map((c) => [c.key, Object.fromEntries(c.entries.map((e) => [e.slug, e]))]));
  const tabs = [{ key: 'overall', title: 'Overall' }, ...categories.map((c) => ({ key: c.key, title: c.title }))];
  const category = categories.find((c) => c.key === selected);

  return (
    <>
      <div className="tabs" role="group" aria-label="Ranking category">
        {tabs.map((tab) => (
          <button key={tab.key} type="button" aria-pressed={selected === tab.key} onClick={() => setSelected(tab.key)}>
            {tab.title}
          </button>
        ))}
      </div>
      {category ? (
        <RankTable
          caption={`${category.title}${category.tier ? ` (${category.tier})` : ''}: ${category.description}. The bar shows the score (longer is better); the line marks Axum.${['speed', 'database', 'pressure', 'endurance'].includes(category.key) ? ' Endpoint columns are requests/s ratios; "*" marks a score where a client-bound run counted with its server efficiency.' : ''}`}
          title={DETAIL[category.key]?.title ?? 'vs Axum'}
          entries={category.entries}
          extra={DETAIL[category.key]?.columns ?? []}
          value={DETAIL[category.key]?.value ?? ((e) => times(e.ratio))}
          cells={DETAIL[category.key]?.cells ?? (() => [])}
          score={(e) => e.score}
          names={names}
        />
      ) : (
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
      )}
    </>
  );
}
