import { clientBound, isMeasured, label } from '../format';

const ENDPOINT = 'tier1.json';

// `vs_axum.json_rps` is the median of the per-round ratios to Axum on the same
// runner (1.0 for Axum itself); absent when the run measured nothing or left
// the metric out.
const jsonRatio = (row) => row.vs_axum?.json_rps ?? null;
const dbRatio = (row) => row.vs_axum?.db_single_rps ?? null;

// `excluded` lists metric groups such as `tier1.db-single`.
const excludedName = (key) => (key.startsWith('tier1.') ? `/${key.slice(6)}` : key);

const times = (value) => (value === null ? '–' : `${value.toFixed(2)}×`);

function notes(row) {
  if (!isMeasured(row)) return `not measured (${row.status})`;
  const out = [];
  const bound = clientBound(row, ENDPOINT);
  if (bound) out.push(bound);
  if (row.status === 'crashed') out.push('stopped during a round');
  if (row.excluded?.length) out.push(`left out: ${row.excluded.map(excludedName).join(', ')}`);
  return out.join('; ');
}

// Every implementation in order of its /json requests/s ratio to Axum. Rows
// without that ratio (not measured, or left out) follow without a position.
export function Ranking({ rows }) {
  const ranked = rows.filter((r) => isMeasured(r) && jsonRatio(r) !== null).sort((a, b) => jsonRatio(b) - jsonRatio(a));
  const unranked = rows.filter((r) => !ranked.includes(r));
  const scale = Math.max(1, ...ranked.map(jsonRatio));
  const bar = (value) =>
    value === null ? null : (
      <span className="bar" aria-hidden="true">
        <span className="bar-fill" style={{ width: `${(value / scale) * 100}%` }} />
        <span className="bar-axum" style={{ left: `${(1 / scale) * 100}%` }} />
      </span>
    );
  return (
    <div className="table-wrap">
      <table className="ranking">
        <caption>Tier 1 /json, higher is faster; the line marks Axum (1.00×)</caption>
        <thead>
          <tr>
            <th scope="col">#</th>
            <th className="text" scope="col">Implementation</th>
            <th className="text" scope="col">/json vs Axum</th>
            <th scope="col">/db-single vs Axum</th>
            <th className="text" scope="col">Language</th>
            <th className="text" scope="col">Notes</th>
          </tr>
        </thead>
        <tbody>
          {[...ranked, ...unranked].map((row, index) => (
            <tr key={row.slug} className={row.is_baseline ? 'baseline' : undefined}>
              <td>{index < ranked.length ? index + 1 : '–'}</td>
              <th scope="row" className="text">{label(row)}</th>
              <td className="text">
                <span className="bar-cell">
                  <span className="bar-value">{times(isMeasured(row) ? jsonRatio(row) : null)}</span>
                  {bar(isMeasured(row) ? jsonRatio(row) : null)}
                </span>
              </td>
              <td>{times(isMeasured(row) ? dbRatio(row) : null)}</td>
              <td className="text">{row.language}</td>
              <td className="text">{notes(row)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
