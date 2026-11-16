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
          noise, and &quot;client-bound&quot; means the load generator, not the server, was the limit, so close
          results at the top are ties.
        </li>
        <li>
          <strong>Rullst is measured twice.</strong> <em>Rullst (as generated)</em> is the application that{' '}
          <code>cargo rullst new</code> and <code>cargo rullst deploy</code> create, with the production middleware
          they turn on: WAF, CSRF protection, secure cookies, security headers and an access log.{' '}
          <em>Rullst (minimal)</em> is Rullst&apos;s router, ORM and <code>html!</code> served like the Axum app,
          without that middleware; it is not how <code>cargo rullst new</code> sets up an application. The gap
          between the two rows shows what the default stack costs.
        </li>
      </ul>
    </section>
  );
}
