// A short guide for readers who do not run benchmarks: what the ratios mean,
// which direction is better, what ties and the overall score are, and what the
// two Rullst rows are. The variant definitions follow frameworks/rullst/README.md
// and frameworks/rullst-minimal/README.md; the rules follow the README.
export function HowToRead() {
  return (
    <section className="howto" aria-labelledby="howto-title">
      <h2 id="howto-title">How to read these results</h2>
      <ul>
        <li>
          <strong>1.00× is Axum.</strong> Every score divides a framework&apos;s result by the result of Axum, a
          small Rust framework used as the reference, measured on the same machine in alternating rounds. 0.50× is
          half of Axum&apos;s result and 2.00× twice. Higher is better in every score: for memory and start-up time
          the ratio is turned around, so a higher score means less RAM or a faster start. In the tables of absolute
          numbers, latency and RAM are better when lower.
        </li>
        <li>
          <strong>Ties and ±.</strong> The machines are shared cloud machines with different CPU models, so results
          vary from run to run. &quot;±6%&quot; next to a score is the margin within which two scores cannot be
          told apart; it comes from an identical copy of Axum measured like the others and from how much each
          framework&apos;s score differed between its runs. Scores that close share a range of positions, such as
          &quot;3–7&quot;: positions 3 to 7 in no particular order.
        </li>
        <li>
          <strong>The categories answer different questions.</strong> <em>Hello world</em>: what a framework costs
          per request when the page is trivial. <em>Database</em>: how it reads, writes and renders rows.{' '}
          <em>Application</em>: what it does with a real request (input, validation, a write, a form with CSRF
          protection, a signed-in user). <em>Memory</em>: how much RAM it needs under load. <em>Startup</em>: how
          fast it starts. <em>Stability</em> (pass or fail): whether it keeps working under heavier load.
        </li>
        <li>
          <strong>The database usually comes first.</strong> In a real application the database is usually the
          limit before the framework is, so a large gap in Hello world shrinks or disappears once requests read and
          write data; Database and Application are closer to what an application does. When a run was limited by
          the database or the load generator rather than the server (&quot;*&quot;), the score compares CPU cost
          per request instead of requests per second.
        </li>
        <li>
          <strong>The overall score is a summary.</strong> It combines the five category scores, with Hello world,
          Database and Application counted twice and Memory and Startup once, for quick reading. The categories are
          the real result: other weights change the order, as the table under the overall ranking shows.
        </li>
        <li>
          <strong>Rullst is measured twice.</strong> <em>Rullst (as generated)</em> is the application that{' '}
          <code>cargo rullst new</code> and <code>cargo rullst deploy</code> create, with the production middleware
          they turn on: WAF, CSRF protection, secure cookies and security headers (and, in the 13.0.0-alpha.5 results
          only, an access log that release could not turn off); it is the ranked Rullst.{' '}
          <em>Rullst (minimal)</em> is Rullst&apos;s router, ORM and <code>html!</code> served through{' '}
          <code>rullst::web::axum::serve</code>, Axum&apos;s own server, bypassing <code>rullst::Server</code> and
          that middleware; it is not how <code>cargo rullst new</code> sets up an application, so it is an unranked
          diagnostic. The gap between the two rows shows what the default stack costs.
        </li>
      </ul>
    </section>
  );
}
