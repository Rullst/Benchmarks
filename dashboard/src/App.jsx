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
      let ramMB = 1;
      if (fw.peakRam.includes("MiB")) ramMB = parseFloat(fw.peakRam);
      if (fw.peakRam.includes("GiB")) ramMB = parseFloat(fw.peakRam) * 1024;
      if (ramMB === 0 || isNaN(ramMB)) ramMB = 9999; // Penalty for failed frameworks

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
          <a href="https://github.com/your-username/Benchmarks/blob/main/benchmarks_results.md" target="_blank" rel="noreferrer" className="btn-primary">
            📄 View Raw Data (Markdown)
          </a>
          <a href="https://github.com/your-username/Benchmarks/" target="_blank" rel="noreferrer" className="btn-secondary">
            ⭐ Star the Repo
          </a>
        </div>
      </header>

      <Methodology />

      <MetricsExplanation />

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
