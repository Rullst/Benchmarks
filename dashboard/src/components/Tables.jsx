import { clientBound, errorRate, isMeasured, label, median, num, paired, range, ratio, serves } from '../format';

// Phase-2 endpoints: how the results name them (bench/common.py ENDPOINT_LABELS).
const APPLICATION = {
  world: 'GET /world/{id}',
  worlds: 'GET /worlds',
  'world-update': 'PUT /world/{id}',
  form: 'POST /form',
  me: 'GET /me',
};

function mechanism(row, kind) {
  const value = row.phase2?.[kind];
  const main = value?.[kind === 'csrf' ? 'design' : 'store'];
  return main ? `${main} (${value.source})` : '–';
}

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

const SUMMARY_ENDPOINTS = ['json', 'html', 'db-single', 'queries', 'updates', 'fortunes'];

export function SummaryTable({ rows }) {
  const columns = [
    name,
    { title: 'Version', text: true, value: (r) => r.framework_version },
    { title: 'Language', text: true, value: (r) => r.language },
    ...SUMMARY_ENDPOINTS.map((ep) => ({
      title: `/${ep} vs Axum`,
      value: (r) => (serves(r, ep) ? ratio(r, `tier1.${ep}.rps`) : 'n/i'),
    })),
    { title: '/json req/s (Axum)', value: (r) => paired(r, 'tier1.json.rps') },
    { title: 'Idle RAM (MiB)', value: (r) => num(median(r, 'tier3.idle_ram_mib'), 1) },
    { title: 'Peak RAM (MiB)', value: (r) => num(median(r, 'tier3.load_ram_peak_mib'), 1) },
    { title: 'Tier 4 errors', value: (r) => errorRate(r, 'tier4.error_rate') },
  ];
  return (
    <>
      <Table columns={columns} rows={rows.filter(isMeasured)} />
      <p className="note">
        Ratios are requests/s divided by Axum&apos;s on the same runner (higher is better). &quot;/json req/s
        (Axum)&quot; is the absolute number with, in brackets, Axum&apos;s on the same runner: absolute numbers come
        from different runners, so compare them only within a row. &quot;n/i&quot;: not implemented yet.
        /queries and /updates use queries=20.
      </p>
    </>
  );
}

export function ApplicationTable({ rows }) {
  const measured = rows.filter(isMeasured);
  if (!measured.some((r) => Object.keys(APPLICATION).some((ep) => serves(r, ep)))) return null;
  const columns = [
    name,
    ...Object.entries(APPLICATION).map(([ep, title]) => ({
      title: `${title} vs Axum`,
      value: (r) => (serves(r, ep) ? ratio(r, `tier1.${ep}.rps`) : 'n/i'),
    })),
    { title: 'CSRF', text: true, value: (r) => (serves(r, 'form') ? mechanism(r, 'csrf') : 'n/i') },
    { title: 'Session store', text: true, value: (r) => (serves(r, 'me') ? mechanism(r, 'session') : 'n/i') },
    { title: 'Hot rows p99 (ms)', value: (r) => num(median(r, 'hot_rows.latency_ms.p99'), 2) },
    { title: 'Hot rows errors', value: (r) => errorRate(r, 'hot_rows.error_rate') },
  ];
  return (
    <>
      <h3>Application endpoints</h3>
      <Table columns={columns} rows={measured} />
      <p className="note">
        CSRF is the design of the form protection (token: a secret the form echoes; fetch-metadata:
        Sec-Fetch-Site/Origin checks) and the session store is each framework&apos;s default for a signed-in user,
        with where the mechanism comes from: POST /form and GET /me compare those defaults, not one common mechanism.
        Hot rows: PUT /world/{'{id}'} on ids 1-10 only, so requests wait for each other&apos;s row locks; reported, not
        ranked.
      </p>
    </>
  );
}

function tier1(endpoint) {
  const base = `tier1.${endpoint}`;
  return [
    name,
    { title: 'req/s', value: (r) => range(r, `${base}.rps`) },
    { title: 'vs Axum', value: (r) => ratio(r, `${base}.rps`) },
    { title: 'Efficiency (req/CPU-s)', value: (r) => num(median(r, `${base}.rps_per_cpu`)) },
    { title: 'vs Axum', value: (r) => ratio(r, `${base}.rps_per_cpu`) },
    { title: 'p50 (ms)', value: (r) => num(median(r, `${base}.latency_ms.p50`), 2) },
    { title: 'p99 (ms)', value: (r) => num(median(r, `${base}.latency_ms.p99`), 2) },
    { title: 'Errors', value: (r) => errorRate(r, `${base}.error_rate`) },
    { title: 'Server CPU (cores)', value: (r) => num(median(r, `${base}.server_cpu_cores`), 2) },
    { title: 'DB CPU (cores)', value: (r) => num(median(r, `${base}.db_cpu_cores`), 2) },
    {
      title: 'Notes',
      text: true,
      value: (r) => {
        if (!serves(r, endpoint)) return 'not implemented yet';
        const notes = [clientBound(r, base)].filter(Boolean);
        if (endpoint === 'form') notes.push(`CSRF: ${mechanism(r, 'csrf')}`);
        if (endpoint === 'me') notes.push(`session: ${mechanism(r, 'session')}`);
        return notes.join('; ');
      },
    },
  ];
}

const HOT_ROWS = [
  name,
  { title: 'req/s', value: (r) => range(r, 'hot_rows.rps') },
  { title: 'vs Axum', value: (r) => ratio(r, 'hot_rows.rps') },
  { title: 'p50 (ms)', value: (r) => num(median(r, 'hot_rows.latency_ms.p50'), 2) },
  { title: 'p99 (ms)', value: (r) => num(median(r, 'hot_rows.latency_ms.p99'), 2) },
  { title: 'p99 vs Axum', value: (r) => ratio(r, 'hot_rows.latency_ms.p99') },
  { title: 'Errors', value: (r) => errorRate(r, 'hot_rows.error_rate') },
  { title: 'Timeouts', value: (r) => num(median(r, 'hot_rows.timeouts')) },
  { title: 'DB CPU (cores)', value: (r) => num(median(r, 'hot_rows.db_cpu_cores'), 2) },
];

const TIER_COLUMNS = {
  tier2: [
    name,
    { title: 'req/s', value: (r) => range(r, 'tier2.rps') },
    { title: 'vs Axum', value: (r) => ratio(r, 'tier2.rps') },
    { title: 'Efficiency (req/CPU-s)', value: (r) => num(median(r, 'tier2.rps_per_cpu')) },
    { title: 'vs Axum', value: (r) => ratio(r, 'tier2.rps_per_cpu') },
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
    { title: 'Tier 1 /json req/s per MiB', value: (r) => num(r.rps_per_mib ?? null, 1) },
    { title: 'Threads', value: (r) => num(median(r, 'idle.tasks')) },
  ],
  tier4: [
    name,
    { title: 'req/s', value: (r) => range(r, 'tier4.rps') },
    { title: 'vs Axum', value: (r) => ratio(r, 'tier4.rps') },
    { title: 'Efficiency (req/CPU-s)', value: (r) => num(median(r, 'tier4.rps_per_cpu')) },
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

export function TierTables({ data, rows: all }) {
  const rows = all.filter(isMeasured);
  const tiers = data.config?.tiers ?? {};
  const t1 = tiers.tier1 ?? { endpoints: [] };
  const t2 = tiers.tier2 ?? {};
  const t3 = tiers.tier3 ?? {};
  const t4 = tiers.tier4 ?? {};
  return (
    <>
      <h3>Tier 1: {t1.connections} connections, {t1.duration_s} s per endpoint</h3>
      <p className="note">
        Efficiency is requests per server CPU-second: what a request costs the server, comparable even when the load
        generator or the database was the limit (client-bound). DB CPU is PostgreSQL&apos;s CPU use.
      </p>
      {t1.endpoints.map((endpoint) => (
        <Table
          key={endpoint}
          caption={APPLICATION[endpoint] ?? data.config?.endpoint_paths?.[endpoint] ?? `/${endpoint}`}
          columns={tier1(endpoint)}
          rows={rows}
        />
      ))}
      {rows.some((r) => median(r, 'hot_rows.rps') !== null) && (
        <>
          <h3>
            Write contention: PUT /world/{'{id}'} on ids 1-{data.config?.hot_rows?.ids ?? 10} (hot rows)
          </h3>
          <p className="note">
            {t1.connections} connections for {t1.duration_s} s write the same few rows, so requests wait for each
            other&apos;s row locks. Reported, not ranked: compare the errors, timeouts and p99 latency.
          </p>
          <Table columns={HOT_ROWS} rows={rows.filter((r) => serves(r, data.config?.hot_rows?.endpoint ?? 'world-update'))} />
        </>
      )}
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
