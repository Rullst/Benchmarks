import React, { useState, useEffect } from 'react';
import { FrameworkCard } from './components/FrameworkCard';
import { RullstAnalysis } from './components/RullstAnalysis';
import { MetricsExplanation } from './components/MetricsExplanation';
import resultsData from './data.json';

function App() {
  const [results, setResults] = useState([]);

  useEffect(() => {
    // Sort by JSON RPS descending as primary metric
    const sorted = [...resultsData].sort((a, b) => b.jsonRps - a.jsonRps);
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
      </header>

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
