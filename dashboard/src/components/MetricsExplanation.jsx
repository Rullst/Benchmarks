import React from 'react';
import './MetricsExplanation.css';

export function MetricsExplanation() {
  return (
    <section className="glass-panel metrics-section animate-fade-in delay-2">
      <div className="metrics-header">
        <h2>What Do These Metrics Mean?</h2>
        <p>Understanding the numbers behind the ranking.</p>
      </div>

      <div className="metrics-grid">
        <div className="metric-card">
          <span className="metric-icon">⚡</span>
          <h4>JSON (Req/sec)</h4>
          <p><strong>Requests Per Second (Tier 1 & 2):</strong> Measures raw throughput when serializing and serving JSON responses. Higher is better, indicating the framework can handle more simultaneous users without queuing.</p>
        </div>

        <div className="metric-card">
          <span className="metric-icon">🗄️</span>
          <h4>DB Single (Req/sec)</h4>
          <p><strong>Database Throughput (Tier 1):</strong> Tests the ORM/Query Builder overhead. It measures how fast the framework can fetch a single record from PostgreSQL. Higher is better.</p>
        </div>

        <div className="metric-card">
          <span className="metric-icon">⏱️</span>
          <h4>Avg Latency</h4>
          <p><strong>Responsiveness (Tier 2):</strong> The average time it takes for the server to respond under heavy load (300 concurrent connections). Lower is better, meaning less waiting time for the user.</p>
        </div>

        <div className="metric-card">
          <span className="metric-icon">🧠</span>
          <h4>Peak RAM</h4>
          <p><strong>Memory Footprint (Tier 3):</strong> The maximum amount of RAM consumed during a stress test. Lower is better, meaning you can run the server on cheaper hardware (like a $5 VPS).</p>
        </div>
      </div>
    </section>
  );
}
