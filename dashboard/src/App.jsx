import { useEffect, useState } from 'react';
import { History } from './components/History';
import { HowToRead } from './components/HowToRead';
import { Ranking } from './components/Ranking';
import { Implementations, NotMeasured, SummaryTable, TierTables } from './components/Tables';
import { date, num } from './format';
import './App.css';

const DATA = `${import.meta.env.BASE_URL}data/`;
const REPO = 'https://github.com/Rullst/Benchmarks';

async function load(name) {
  const response = await fetch(DATA + name, { cache: 'no-cache' });
  if (!response.ok) throw new Error(`${name}: HTTP ${response.status}`);
  return response.json();
}

// Backtick-quoted parts of a note render as code.
function inlineCode(text) {
  return text.split('`').map((part, i) => (i % 2 ? <code key={i}>{part}</code> : part));
}

function Notice({ data }) {
  const env = data.environment ?? {};
  return (
    <section className="notice" aria-label="About these results">
      <p>
        Measured on <strong>{date(data.measured_from || data.generated_at)}</strong> with{' '}
        <strong>Rullst {data.rullst_version || 'unknown'}</strong> on GitHub-hosted runners ({env.cpu_model ?? 'CPU unknown'},{' '}
        {env.cpu_count} vCPUs, {num((env.memory_total_mib ?? 0) / 1024)} GiB RAM); each server was limited to 2 vCPUs
        and 2 GiB. Values are medians of {data.run?.rounds} rounds.
      </p>
      <p>
        These results update automatically when a new Rullst version is published on crates.io. Last update:{' '}
        <strong>{date(data.generated_at)}</strong>
        {data.run?.url && (
          <>
            {' '}(<a href={data.run.url}>workflow run</a>)
          </>
        )}
        .
      </p>
      {data.note && (
        <p>
          <strong>Note:</strong> {inlineCode(data.note)}
        </p>
      )}
    </section>
  );
}

export default function App() {
  const [state, setState] = useState({ status: 'loading' });

  useEffect(() => {
    Promise.all([load('latest.json'), load('versions.json')])
      // `results` holds the measured implementations, `not_measured` the others
      // (shape rullst.benchmarks.latest.v1, see the README).
      .then(([data, index]) =>
        setState({ status: 'ready', data, index, rows: [...(data.results ?? []), ...(data.not_measured ?? [])] }),
      )
      .catch((error) => setState({ status: 'empty', error: String(error) }));
  }, []);

  return (
    <main className="container">
      <header>
        <h1>Rullst Benchmarks</h1>
        <p className="lede">
          HTTP benchmarks of Rullst and other web frameworks, measured by a GitHub Actions workflow that anyone can
          rerun. Seven endpoints (<code>/text</code>, <code>/json</code>, <code>/db-single</code>, <code>/html</code>,
          and the database endpoints <code>/queries</code>, <code>/updates</code>, <code>/fortunes</code>), four load
          tiers, conformance-checked responses.
        </p>
        <nav className="links">
          <a href={`${REPO}#method`}>Method and limitations</a>
          <a href={`${REPO}/blob/main/benchmarks_results.md`}>Results (Markdown)</a>
          <a href={`${DATA}latest.json`}>latest.json</a>
          <a href={REPO}>Source</a>
        </nav>
      </header>

      {state.status === 'loading' && <p className="note">Loading results…</p>}
      {state.status === 'empty' && (
        <p className="note">
          No results have been published yet. Results from before the suite was rebuilt are kept, for the record only, in{' '}
          <a href={`${REPO}/blob/main/history/2026-06-22-laptop.md`}>the history folder</a>.
        </p>
      )}
      {state.status === 'ready' && (
        <>
          <HowToRead />
          <Notice data={state.data} />
          <section>
            <h2>Ranking</h2>
            <p className="note">
              An overall ranking and one per category: Speed and Database (Tier 1), Under pressure (Tier 2), Memory
              (Tier 3), Endurance (Tier 4) and Startup. &quot;3=&quot; is a shared position (a tie); Axum is the
              reference and has no position; an implementation with a missing or left-out result, or an endpoint it
              does not serve yet, is listed as incomplete, without a position. &quot;How to read these results&quot;
              above explains the scores.
            </p>
            <Ranking rankings={state.data.rankings} rows={state.rows} />
          </section>
          <section>
            <h2>Summary</h2>
            <SummaryTable rows={state.rows} />
            {state.rows
              .filter((row) => row.excluded?.length)
              .map((row) => (
                <p key={row.slug} className="note">
                  <strong>Correction, {row.name}:</strong> {row.problem} Left-out results are shown as –.
                </p>
              ))}
            <NotMeasured rows={state.rows} />
          </section>
          <section>
            <h2>Tiers</h2>
            <TierTables data={state.data} rows={state.rows} />
          </section>
          <section>
            <h2>Rullst across versions</h2>
            <History index={state.index} />
          </section>
          <section>
            <h2>Implementations</h2>
            <p className="note">
              Each folder under <a href={`${REPO}/tree/main/frameworks`}>frameworks/</a> has a README with its
              configuration and the reasons for it.
            </p>
            <Implementations rows={state.rows} />
          </section>
        </>
      )}
      <footer>
        <p>
          Results published before the rebuild (22 June 2026, a laptop, not reproducible) are kept in{' '}
          <a href={`${REPO}/blob/main/history/2026-06-22-laptop.md`}>history/2026-06-22-laptop.md</a>; they are not
          comparable.
        </p>
      </footer>
    </main>
  );
}
