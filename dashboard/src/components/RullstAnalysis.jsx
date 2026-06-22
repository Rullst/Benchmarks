import React from 'react';
import './RullstAnalysis.css';

export function RullstAnalysis() {
  return (
    <section className="glass-panel analysis-section animate-fade-in delay-3">
      <div className="analysis-header">
        <h2 className="text-gradient">Why Rullst?</h2>
        <p>A deep dive into the architecture that makes Rullst incredibly fast.</p>
      </div>

      <div className="analysis-grid">
        <div className="analysis-card win-card">
          <div className="icon">🚀</div>
          <h3>Where Rullst Wins</h3>
          <ul className="analysis-list">
            <li>
              <strong>Unmatched Latency:</strong> Built purely on top of Rust's Tokio and Axum, Rullst eliminates the garbage collection pauses found in JVM or Node.js frameworks.
            </li>
            <li>
              <strong>Raw Throughput:</strong> It easily maxes out available CPU cores, serving tens of thousands of requests per second with negligible memory footprint.
            </li>
            <li>
              <strong>Developer Ergonomics:</strong> The `#[routes]` macro provides a developer experience similar to Express or Spring, but with the performance of low-level Rust.
            </li>
          </ul>
        </div>

        <div className="analysis-card trade-card">
          <div className="icon">⚖️</div>
          <h3>Trade-offs & Challenges</h3>
          <ul className="analysis-list">
            <li>
              <strong>Ecosystem Maturity:</strong> Unlike Spring Boot or Next.js, Rullst's ecosystem is still nascent. You might need to write custom middleware for edge cases.
            </li>
            <li>
              <strong>Learning Curve:</strong> Adopting Rullst requires understanding Rust's ownership model, which can be challenging for teams migrating from Python or JavaScript.
            </li>
            <li>
              <strong>Compilation Times:</strong> Building the project from scratch (especially with SQLx macros) takes significantly longer than hot-reloading in Next.js.
            </li>
          </ul>
        </div>
      </div>
    </section>
  );
}
