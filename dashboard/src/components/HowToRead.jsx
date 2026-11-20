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
          is 1.00. <em>Hello world</em> (Tier 1, 125 connections) is the geometric mean of the capacity ratios of
          /text, /json and /html; <em>Database</em> of /db-single, /queries and /updates (20 random rows per
          request) and /fortunes; <em>Application</em> of GET /world/{'{id}'}, GET /worlds, PUT /world/{'{id}'},
          POST /form (with each framework&apos;s CSRF check) and GET /me (each framework&apos;s default session
          store). A run counts with its requests/s ratio when neither server was client-bound, and otherwise with
          its ratio of requests per CPU-second of the server and PostgreSQL together (marked &quot;*&quot;), so a
          framework is charged for the database work its queries cause; a run limited by the load generator while
          a server used less than 75% of its vCPUs is not comparable. A run with more than 1% errors gets no
          score. <em>Memory</em> is Axum&apos;s RAM high-water mark (after the load tiers) divided by the
          framework&apos;s, and <em>Startup</em> Axum&apos;s start-up time divided by the framework&apos;s, with
          every value counted as at least 64 MiB and 1 s. <em>Stability</em> (Tiers 2 and 4 on /json, 300 and 500
          connections) is a pass, warn or fail check, not a score. An overall score (the geometric mean of the
          five) is shown only when the results publish one; the weighting would be a choice, not a fact about the
          frameworks.
        </li>
        <li>
          <strong>Ties and incomplete rows.</strong> Scores within the tie margin of their category share a
          position, written &quot;1=&quot;. The margin is the largest of the A/A control&apos;s deviation from 1.00
          (an identical copy of Axum measured like the others), the root of the sum of squares of the two
          implementations&apos; spreads between their jobs (runners, often with different CPU models) and the
          median of those spreads, so smaller differences are noise. Start-up times within
          0.25 s also share a position. A framework with a missing or left-out result, or one that does not serve
          an endpoint yet, is listed as incomplete, without a position in that category, rather than ranked on
          fewer metrics.
        </li>
        <li>
          <strong>Rullst is measured twice.</strong> <em>Rullst (as generated)</em> is the application that{' '}
          <code>cargo rullst new</code> and <code>cargo rullst deploy</code> create, with the production middleware
          they turn on: WAF, CSRF protection, secure cookies, security headers and an access log (on in the
          13.0.0-alpha.5 results, a release that cannot turn it off; off from 13.0.0-alpha.6, like logging in every
          implementation).{' '}
          <em>Rullst (minimal)</em> is Rullst&apos;s router, ORM and <code>html!</code> served like the Axum app,
          without that middleware; it is not how <code>cargo rullst new</code> sets up an application, so it is
          an unranked diagnostic shown next to the reference. The gap between the two rows shows what the default
          stack costs.
        </li>
      </ul>
    </section>
  );
}
