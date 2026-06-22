import React from 'react';
import './Methodology.css';

export function Methodology() {
  return (
    <section className="glass-panel methodology-section animate-fade-in delay-2">
      <div className="methodology-header">
        <h2>Benchmark Methodology</h2>
        <p>Testing environment and rules (Last Updated: <strong>June 22, 2026</strong>)</p>
      </div>

      <div className="methodology-content">
        <div className="hardware-specs">
          <h3>🖥️ Official Tested Hardware</h3>
          <ul>
            <li><strong>Processor (CPU):</strong> AMD Ryzen 7 5700U (8 Cores / 16 Threads)</li>
            <li><strong>Memory (RAM):</strong> 8GB</li>
            <li><strong>Operating System:</strong> Windows 11 (Docker with WSL2)</li>
            <li><strong>Database:</strong> PostgreSQL 15 (Dedicated Container)</li>
          </ul>
        </div>

        <div className="tiers-explanation">
          <h3>🔬 The 4-Tier Stress Test</h3>
          <div className="tier-list">
            <div className="tier-item">
              <span className="tier-badge">Tier 1</span>
              <div>
                <strong>Fast Load:</strong> 125 concurrent connections for 10s. Evaluates raw baseline JSON and Database RPS.
              </div>
            </div>
            <div className="tier-item">
              <span className="tier-badge">Tier 2</span>
              <div>
                <strong>High Concurrency:</strong> 300 concurrent connections for 30s. Measures P99 Latency under heavy load.
              </div>
            </div>
            <div className="tier-item">
              <span className="tier-badge">Tier 3</span>
              <div>
                <strong>Resource Efficiency:</strong> Idle vs 200 concurrent connections. Captures maximum RAM consumed.
              </div>
            </div>
            <div className="tier-item">
              <span className="tier-badge">Tier 4</span>
              <div>
                <strong>Resilience:</strong> 500 concurrent connections for an intense 2-minute marathon. Tests for memory leaks and crashes.
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
