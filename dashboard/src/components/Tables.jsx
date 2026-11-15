import { clientBound, errorRate, isMeasured, label, median, num, range, ratio } from '../format';

function Table({ caption, columns, rows }) {
  return (
    <div className="table-wrap">
      <table>
        {caption && <caption>{caption}</caption>}
        <thead>
          <tr>
            {columns.map((c, index) => (
              <th key={index} className={c.text ? 'text' : undefined} scope="col">{c.title}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.slug} className={row.is_baseline ? 'baseline' : undefined}>
              {columns.map((c, index) =>
                index === 0 ? (
                  <th key={index} scope="row" className="text">{c.value(row)}</th>
                ) : (
                  <td key={index} className={c.text ? 'text' : undefined}>{c.value(row)}</td>
                ),
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const name = { title: 'Implementation', text: true, value: label };

export function SummaryTable({ rows }) {
  const columns = [
    name,
    { title: 'Version', text: true, value: (r) => r.framework_version },
    { title: 'Language', text: true, value: (r) => r.language },
    { title: '/json req/s', value: (r) => num(median(r, 'tier1.json.rps')) },
    { title: 'vs Axum', value: (r) => ratio(r, 'tier1.json.rps') },
    { title: '/db-single req/s', value: (r) => num(median(r, 'tier1.db-single.rps')) },
    { title: 'vs Axum', value: (r) => ratio(r, 'tier1.db-single.rps') },
    { title: '/html req/s', value: (r) => num(median(r, 'tier1.html.rps')) },
    { title: 'Tier 2 p99 (ms)', value: (r) => num(median(r, 'tier2.latency_ms.p99'), 2) },
    { title: 'Idle RAM (MiB)', value: (r) => num(median(r, 'tier3.idle_ram_mib'), 1) },
    { title: 'Peak RAM (MiB)', value: (r) => num(median(r, 'tier3.load_ram_peak_mib'), 1) },
    { title: 'Tier 4 errors', value: (r) => errorRate(r, 'tier4.error_rate') },
    { title: 'req/s per MiB', value: (r) => num(r.rps_per_mib ?? null, 1) },
  ];
  return <Table columns={columns} rows={rows.filter(isMeasured)} />;
}

function tier1(endpoint) {
  const base = `tier1.${endpoint}`;
  return [
    name,
    { title: 'req/s', value: (r) => range(r, `${base}.rps`) },
    { title: 'vs Axum', value: (r) => ratio(r, `${base}.rps`) },
    { title: 'p50 (ms)', value: (r) => num(median(r, `${base}.latency_ms.p50`), 2) },
    { title: 'p99 (ms)', value: (r) => num(median(r, `${base}.latency_ms.p99`), 2) },
    { title: 'Errors', value: (r) => errorRate(r, `${base}.error_rate`) },
    { title: 'Server CPU (cores)', value: (r) => num(median(r, `${base}.server_cpu_cores`), 2) },
    { title: 'Notes', text: true, value: (r) => clientBound(r, base) },
  ];
}

const TIER_COLUMNS = {
  tier2: [
    name,
    { title: 'req/s', value: (r) => range(r, 'tier2.rps') },
    { title: 'vs Axum', value: (r) => ratio(r, 'tier2.rps') },
    { title: 'p50 (ms)', value: (r) => num(median(r, 'tier2.latency_ms.p50'), 2) },
    { title: 'p99 (ms)', value: (r) => range(r, 'tier2.latency_ms.p99', 2) },
    { title: 'p99 vs Axum', value: (r) => ratio(r, 'tier2.latency_ms.p99') },
    { title: 'Errors', value: (r) => errorRate(r, 'tier2.error_rate') },
    { title: 'Timeouts', value: (r) => num(median(r, 'tier2.timeouts')) },
    { title: 'Notes', text: true, value: (r) => clientBound(r, 'tier2') },
  ],
  tier3: [
    name,
    { title: 'Idle RAM (MiB)', value: (r) => range(r, 'tier3.idle_ram_mib', 1) },
    { title: 'vs Axum', value: (r) => ratio(r, 'tier3.idle_ram_mib') },
    { title: 'Idle CPU', value: (r) => num(median(r, 'tier3.idle_cpu_cores'), 3) },
    { title: 'Peak RAM (MiB)', value: (r) => range(r, 'tier3.load_ram_peak_mib', 1) },
    { title: 'vs Axum', value: (r) => ratio(r, 'tier3.load_ram_peak_mib') },
    { title: 'Load CPU', value: (r) => num(median(r, 'tier3.load_cpu_cores'), 2) },
    { title: 'req/s', value: (r) => num(median(r, 'tier3.rps')) },
    { title: 'Threads', value: (r) => num(median(r, 'idle.tasks')) },
  ],
  tier4: [
    name,
    { title: 'req/s', value: (r) => range(r, 'tier4.rps') },
    { title: 'vs Axum', value: (r) => ratio(r, 'tier4.rps') },
    { title: 'p99 (ms)', value: (r) => num(median(r, 'tier4.latency_ms.p99'), 2) },
    { title: 'Errors', value: (r) => errorRate(r, 'tier4.error_rate') },
    { title: 'Timeouts', value: (r) => num(median(r, 'tier4.timeouts')) },
    { title: 'RAM at end (MiB)', value: (r) => num(median(r, 'tier4.ram_end_mib'), 1) },
    { title: 'RAM growth (MiB)', value: (r) => num(median(r, 'tier4.ram_growth_mib'), 1) },
    {
      title: 'Notes',
      text: true,
      value: (r) => {
        const f = r.flags ?? {};
        const notes = [];
        if (f.crashed_rounds) notes.push(`stopped in ${f.crashed_rounds}/${f.rounds} rounds`);
        if (f.ram_growing_rounds) notes.push(`RAM still growing (${f.ram_growing_rounds}/${f.rounds})`);
        if (r.maturity_note) notes.push(r.maturity_note);
        return notes.join('; ');
      },
    },
  ],
};

export function TierTables({ data }) {
  const rows = data.implementations.filter(isMeasured);
  const tiers = data.config?.tiers ?? {};
  const t1 = tiers.tier1 ?? { endpoints: [] };
  const t2 = tiers.tier2 ?? {};
  const t3 = tiers.tier3 ?? {};
  const t4 = tiers.tier4 ?? {};
  return (
    <>
      <h3>Tier 1: {t1.connections} connections, {t1.duration_s} s per endpoint</h3>
      {t1.endpoints.map((endpoint) => (
        <Table key={endpoint} caption={`/${endpoint}`} columns={tier1(endpoint)} rows={rows} />
      ))}
      <h3>Tier 2: /{t2.endpoint}, {t2.connections} connections, {t2.duration_s} s</h3>
      <Table columns={TIER_COLUMNS.tier2} rows={rows} />
      <h3>Tier 3: idle, then /{t3.endpoint} with {t3.connections} connections for {t3.duration_s} s</h3>
      <p className="note">Idle is measured after start-up, before any load. CPU is in cores (2.00 = both server vCPUs busy).</p>
      <Table columns={TIER_COLUMNS.tier3} rows={rows} />
      <h3>Tier 4: /{t4.endpoint}, {t4.connections} connections for {t4.duration_s} s</h3>
      <p className="note">
        RAM growth compares the middle and the last tenth of the test. &quot;Still growing&quot; means it rose by more than
        10% and 8 MiB; for garbage-collected runtimes this can be heap growth rather than a leak.
      </p>
      <Table columns={TIER_COLUMNS.tier4} rows={rows} />
    </>
  );
}

export function NotMeasured({ rows }) {
  const failed = rows.filter((r) => !isMeasured(r));
  if (!failed.length) return null;
  const columns = [
    name,
    { title: 'Status', text: true, value: (r) => r.status },
    { title: 'Reason', text: true, value: (r) => r.problem },
  ];
  return (
    <>
      <h3>Not measured</h3>
      <p className="note">A failed conformance check means at least one endpoint did not return the expected response.</p>
      <Table columns={columns} rows={failed} />
    </>
  );
}

export function Implementations({ rows }) {
  const columns = [
    name,
    { title: 'Version', text: true, value: (r) => r.framework_version },
    { title: 'Runtime', text: true, value: (r) => r.runtime },
    { title: 'Server', text: true, value: (r) => r.server },
    { title: 'Workers', text: true, value: (r) => r.workers },
    { title: 'Database layer', text: true, value: (r) => r.database_layer },
    { title: 'Templates', text: true, value: (r) => r.template_engine },
    { title: 'Logging', text: true, value: (r) => r.logging },
  ];
  return <Table columns={columns} rows={rows} />;
}
