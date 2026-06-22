import React from 'react';
import './FrameworkCard.css';

export function FrameworkCard({ rank, name, language, jsonRps, dbRps, latency, peakRam, efficiencyScore, stars, highlight, status }) {
  const renderStars = () => {
    return Array.from({ length: 5 }).map((_, i) => (
      <span key={i} className={`star ${i < stars ? 'filled' : 'empty'}`}>★</span>
    ));
  };

  return (
    <div className={`glass-panel framework-card animate-fade-in delay-1 ${rank <= 3 ? 'top-tier' : ''}`}>
      <div className="card-header">
        <div className="title-group">
          <span className="rank-badge">#{rank}</span>
          <h3>{name}</h3>
        </div>
        <span className="language-badge">{language}</span>
      </div>
      
      {highlight && <div className="highlight-badge">{highlight}</div>}

      <div className="stats-container">
        <div className="stat-row">
          <span className="stat-label">Efficiency (RPS/MB):</span>
          <span className="stat-value" style={{ color: '#10b981' }}>{efficiencyScore.toLocaleString()}</span>
        </div>
        <div className="stat-row">
          <span className="stat-label">JSON (Req/sec):</span>
          <span className="stat-value">{jsonRps.toLocaleString()}</span>
        </div>
        <div className="stat-row">
          <span className="stat-label">Peak RAM:</span>
          <span className="stat-value">{peakRam}</span>
        </div>
        <div className="stat-row">
          <span className="stat-label">Tier 4 Status:</span>
          <span className={`stat-value ${status === 'Passed' ? 'passed' : 'failed'}`}>{status}</span>
        </div>
      </div>

      <div className="card-footer">
        <div className="rating">
          {renderStars()}
        </div>
      </div>
    </div>
  );
}
