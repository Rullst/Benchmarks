import React from 'react';
import './FrameworkCard.css';

export function FrameworkCard({ name, language, textRps, dbRps, stars, highlight }) {
  const renderStars = () => {
    return Array.from({ length: 5 }).map((_, i) => (
      <span key={i} className={`star ${i < stars ? 'filled' : 'empty'}`}>★</span>
    ));
  };

  return (
    <div className="glass-panel framework-card animate-fade-in delay-1">
      <div className="card-header">
        <h3>{name}</h3>
        <span className="language-badge">{language}</span>
      </div>
      
      {highlight && <div className="highlight-badge">{highlight}</div>}

      <div className="stats-container">
        <div className="stat-row">
          <span className="stat-label">Text (Req/sec):</span>
          <span className="stat-value">{textRps.toLocaleString()}</span>
        </div>
        <div className="stat-row">
          <span className="stat-label">DB Single (Req/sec):</span>
          <span className="stat-value">{dbRps.toLocaleString()}</span>
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
