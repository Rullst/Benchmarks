import React from 'react';
import './FrameworkCard.css';

export function FrameworkCard({ rank, name, language, jsonRps, dbRps, latency, peakRam, stars, highlight, status }) {
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
          <span className="stat-label">JSON (Req/sec):</span>
          <span className="stat-value">{jsonRps.toLocaleString()}</span>
        </div>
        <div className="stat-row">
          <span className="stat-label">DB Single (Req/sec):</span>
          <span className="stat-value">{dbRps.toLocaleString()}</span>
        </div>
        <div className="stat-row">
          <span className="stat-label">Latency (P99):</span>
          <span className="stat-value">{latency}</span>
        </div>
        <div className="stat-row">
          <span className="stat-label">Peak RAM:</span>
          <span className="stat-value">{peakRam}</span>
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
