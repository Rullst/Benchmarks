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

        <div className="analysis-card ai-card">
          <div className="icon">🤖</div>
          <h3>AI-First & Modern Features</h3>
          <ul className="analysis-list">
            <li>
              <strong>AI-First Architecture:</strong> Rullst is fundamentally designed for the AI era. It natively supports deep integration with LLMs and AI agents to write, refactor, and maintain your codebase seamlessly.
            </li>
            <li>
              <strong>Memory Safety:</strong> Leveraging Rust's absolute ownership model, Rullst completely eliminates entire classes of bugs (like null pointer dereferences and data races) at compile-time.
            </li>
            <li>
              <strong>Uncompromising Ergonomics:</strong> Despite being a powerhouse, it prioritizes a gorgeous Developer Experience. You get lightning-fast speeds without fighting the compiler, allowing for rapid iteration.
            </li>
          </ul>
        </div>
      </div>
    </section>
  );
}
