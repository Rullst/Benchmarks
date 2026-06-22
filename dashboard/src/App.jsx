import React, { useState, useEffect } from 'react';
import { FrameworkCard } from './components/FrameworkCard';
import { RullstAnalysis } from './components/RullstAnalysis';
import { MetricsExplanation } from './components/MetricsExplanation';
import { Methodology } from './components/Methodology';
import resultsData from './data.json';

function App() {
  const [results, setResults] = useState([]);

  useEffect(() => {
    // Parse Peak RAM to MB and calculate Efficiency Score (RPS / MB)
    const processedData = resultsData.map(fw => {
      if (fw.status === 'Failed') return { ...fw, efficiencyScore: 0 };
      
      let ramMB = parseFloat(fw.peakRam) || 1;
      if (fw.peakRam.includes("GiB")) ramMB *= 1024;

      const efficiency = fw.jsonRps / ramMB;
      return { ...fw, efficiencyScore: Math.round(efficiency) };
    });

    // Sort by Efficiency Score descending as the true modern ranking metric
    const sorted = processedData.sort((a, b) => b.efficiencyScore - a.efficiencyScore);
    setResults(sorted);
  }, []);

  return (
    <div className="container">
      <header className="header animate-fade-in">
        <h1>
          Rullst <span className="text-gradient">Benchmarks</span>
        </h1>
        <p>
          A comprehensive performance analysis comparing Rullst against the industry's most popular web frameworks.
        </p>
        <div style={{ marginTop: '1.5rem', display: 'flex', gap: '1rem', justifyContent: 'center' }}>
          <a href="https://github.com/Rullst/Benchmarks/blob/main/benchmarks_results.md" target="_blank" rel="noreferrer" className="btn-primary">
            📄 View Raw Data (Markdown)
          </a>
          <a href="https://github.com/Rullst/Benchmarks/" target="_blank" rel="noreferrer" className="btn-secondary">
            ⭐ Star the Repo
          </a>
        </div>
      </header>

      <Methodology />

      <MetricsExplanation />

      <div className="glass-panel" style={{ marginTop: '2rem', padding: '1.5rem', borderLeft: '4px solid #ef4444', backgroundColor: 'rgba(239, 68, 68, 0.05)' }}>
        <h3 style={{ color: '#ef4444', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          ⚠️ About "Failed" Frameworks
        </h3>
        <p style={{ color: 'var(--text-secondary)', lineHeight: '1.5' }}>
          Frameworks that show a <strong>Failed</strong> status (like Laravel or Next.js) usually collapsed during the <strong>Tier 4 Stress Test</strong> (500 concurrent connections for 2 minutes). While they may achieve high Request-Per-Second numbers in short bursts, their underlying worker architecture or garbage collection could not sustain a prolonged heavy load without crashing the container or leaking memory.
        </p>
      </div>

      <div className="framework-grid" style={{ marginTop: '3rem' }}>
        {results.map((fw, index) => (
          <FrameworkCard 
            key={fw.name}
            rank={index + 1}
            name={fw.name}
            language={fw.language}
            jsonRps={fw.jsonRps}
            dbRps={fw.dbRps}
            latency={fw.latency}
            peakRam={fw.peakRam}
            efficiencyScore={fw.efficiencyScore}
            stars={fw.stars}
            highlight={fw.highlight}
            status={fw.status}
          />
        ))}
      </div>

      <RullstAnalysis />
    </div>
  );
}

export default App;
