// A short guide for readers who do not run benchmarks: what the ratios mean,
// which direction is better and what the two Rullst rows are. The variant
// definitions follow frameworks/rullst/README.md and frameworks/rullst-minimal/README.md.
export function HowToRead() {
  return (
    <section className="howto" aria-labelledby="howto-title">
      <h2 id="howto-title">How to read these results</h2>
      <ul>
        <li>
          <strong>1.00× means &quot;the same as Axum&quot;.</strong> Every &quot;vs Axum&quot; number is a
          framework&apos;s result divided by the result of Axum, the baseline (a Rust framework run with no extra
          middleware), measured on the same machine in alternating rounds. 0.50× on requests/s is half as many
          requests per second as Axum; 2.00× is twice as many.
        </li>
        <li>
          <strong>Which direction is better.</strong> Requests/s: higher is better, so above 1.00× is faster than
          Axum. Latency (p50, p99) and RAM: lower is better, so below 1.00× is lower than Axum. Errors and timeouts:
          lower is better, and 0 is the goal.
        </li>
        <li>
          <strong>Compare the ratios, not the absolute numbers.</strong> Each framework is measured in its own job
          on a GitHub-hosted machine, and those machines differ (CPU model, other virtual machines on the same host),
          so two absolute numbers in different rows can come from different hardware. The ratio compares a framework
          with Axum on its own machine, which cancels most of that difference. Differences of a few percent are
          noise. &quot;Client-bound&quot; means the load generator or the database, not the server, was the limit:
          the server could have answered more, so for those runs compare its efficiency (requests per server
          CPU-second), as the ranking does. The summary shows, next to each absolute number, Axum&apos;s value from the
          same machine.
        </li>
        <li>
          <strong>How the ranking is computed.</strong> Each category has a score where higher is better and Axum
          is 1.00. <em>Speed</em> (Tier 1, 125 connections) is the geometric mean of the requests/s ratios of
          /text, /json, /db-single and /html; <em>Database</em> (Tier 1) of /queries and /updates (20 random rows
          per request) and /fortunes. <em>Under pressure</em> (Tier 2, 300 connections for 30 s) and{' '}
          <em>Endurance</em> (Tier 4, 500 connections for 2 minutes) are requests/s ratios; Endurance also lists
          errors, timeouts, RAM still growing and stops. In these four categories, a run where either server was
          client-bound counts with its server efficiency ratio instead of its requests/s ratio (marked
          &quot;*&quot;). <em>Memory</em> (Tier 3) is 1 divided by the peak RAM ratio, so using half of
          Axum&apos;s RAM scores 2.00 (the table also shows the RAM ratio itself). <em>Startup</em> is Axum&apos;s
          start-up time divided by the framework&apos;s; the harness checks every 0.25 s, so times below 0.25 s
          count as equal. The <strong>overall score</strong> is the geometric mean of the six category scores,
          each weighted equally (one sixth). That weighting is a choice, not a fact about the frameworks: the
          per-category rankings are the detail, and the one that matters depends on your application.
        </li>
        <li>
          <strong>Ties and incomplete rows.</strong> Equal scores share a position, written &quot;1=&quot;, and
          so do start-up times within 0.25 s. A framework with a missing or left-out result (for example a
          correction), or one that does not serve an endpoint yet, is listed as incomplete, without a position in
          that category or overall, rather than ranked on fewer metrics.
        </li>
        <li>
          <strong>Rullst is measured twice.</strong> <em>Rullst (as generated)</em> is the application that{' '}
          <code>cargo rullst new</code> and <code>cargo rullst deploy</code> create, with the production middleware
          they turn on: WAF, CSRF protection, secure cookies, security headers and an access log (on in the
          13.0.0-alpha.5 results, a release that cannot turn it off; off from 13.0.0-alpha.6, like logging in every
          implementation).{' '}
          <em>Rullst (minimal)</em> is Rullst&apos;s router, ORM and <code>html!</code> served like the Axum app,
          without that middleware; it is not how <code>cargo rullst new</code> sets up an application. The gap
          between the two rows shows what the default stack costs.
        </li>
      </ul>
    </section>
  );
}
