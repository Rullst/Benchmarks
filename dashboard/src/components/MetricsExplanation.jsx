import React from 'react';
import './MetricsExplanation.css';

export function MetricsExplanation() {
  return (
    <section className="glass-panel metrics-section animate-fade-in delay-2">
      <div className="metrics-header">
        <h2>What Do These Metrics Mean?</h2>
        <p>
          <strong>How the Ranking Works:</strong> Frameworks are sorted by their <strong>Efficiency Score</strong>, which is calculated by dividing their <em>JSON Requests Per Second</em> by their <em>Peak RAM</em> in Megabytes. This means the highest-ranked frameworks are those that serve the most traffic while consuming the least amount of memory. Frameworks that fail the Stress Test receive a score of 0.
        </p>
      </div>

      <div className="metrics-grid">
        <div className="metric-card">
          <span className="metric-icon">⚡</span>
          <h4>JSON (Req/sec)</h4>
          <p><strong>Raw Throughput (Tier 1):</strong> Measures how many requests per second the framework handles when serving JSON. Higher is better.</p>
        </div>

        <div className="metric-card">
          <span className="metric-icon">🗄️</span>
          <h4>DB Single (Req/sec)</h4>
          <p><strong>Database Throughput:</strong> Tests the ORM/Query Builder overhead fetching a single record from PostgreSQL. Higher is better.</p>
        </div>

        <div className="metric-card">
          <span className="metric-icon">⏱️</span>
          <h4>Avg Latency</h4>
          <p><strong>Responsiveness (Tier 2):</strong> The average time to respond under heavy load (300 concurrent connections). Lower is better.</p>
        </div>

        <div className="metric-card">
          <span className="metric-icon">🧠</span>
          <h4>Peak RAM</h4>
          <p><strong>Memory Footprint (Tier 3):</strong> The maximum RAM consumed during a stress test. Lower means cheaper hardware hosting.</p>
        </div>

        <div className="metric-card">
          <span className="metric-icon">🛡️</span>
          <h4>Status</h4>
          <p><strong>Resilience (Tier 4):</strong> Did the framework survive the 2-minute marathon with 500 connections? "Passed" means no memory leaks or crashes.</p>
        </div>

        <div className="metric-card">
          <span className="metric-icon">⭐</span>
          <h4>Star Rating</h4>
          <p><strong>Raw Speed Tier:</strong> 5 Stars for Elite throughput (&gt;80k RPS), 4 Stars for High, and 3 for Standard. <br/><br/><em>Note: A framework can earn 5 stars for being incredibly fast, but still get a "Failed" status if its architecture breaks under heavy pressure!</em></p>
        </div>
      </div>
    </section>
  );
}
