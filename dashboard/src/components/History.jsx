import { date, num } from '../format';

const RATIOS = [
  ['tier1.json.rps', '/json req/s'],
  ['tier1.db-single.rps', '/db-single req/s'],
  ['tier1.html.rps', '/html req/s'],
  ['tier2.latency_ms.p99', 'Tier 2 p99'],
  ['tier3.load_ram_peak_mib', 'Peak RAM'],
];

const VARIANTS = [
  ['rullst', 'as generated'],
  ['rullst-minimal', 'minimal'],
];

// One row per measured Rullst version: each variant's ratios to Axum
// measured on the same runner, the comparable number across runs.
export function History({ index }) {
  const versions = [...(index?.versions ?? [])].reverse();
  if (!versions.length) return <p className="note">No Rullst version has been measured yet.</p>;
  return (
    <div className="table-wrap">
      <table>
        <caption>Ratio to Axum (1.00 = same as Axum; above 1 is more requests/s, or more latency or RAM)</caption>
        <thead>
          <tr>
            <th className="text" scope="col">Rullst version</th>
            <th className="text" scope="col">Measured</th>
            <th className="text" scope="col">Variant</th>
            {RATIOS.map(([key, title]) => (
              <th key={key} scope="col">{title}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {versions.flatMap((entry) =>
            VARIANTS.map(([slug, variant], i) => {
              const impl = entry.implementations?.[slug];
              return (
                <tr key={`${entry.version}-${slug}`}>
                  {i === 0 && (
                    <th className="text" scope="rowgroup" rowSpan={VARIANTS.length}>
                      <a href={`${import.meta.env.BASE_URL}data/${entry.file}`}>{entry.version}</a>
                    </th>
                  )}
                  {i === 0 && <td className="text" rowSpan={VARIANTS.length}>{date(entry.measured_from)}</td>}
                  <td className="text">{variant}</td>
                  {RATIOS.map(([key]) => (
                    <td key={key}>
                      {impl?.status === 'measured' || impl?.status === 'crashed' ? num(impl.ratios?.[key] ?? null, 2) : impl?.status ?? '–'}
                    </td>
                  ))}
                </tr>
              );
            }),
          )}
        </tbody>
      </table>
    </div>
  );
}
