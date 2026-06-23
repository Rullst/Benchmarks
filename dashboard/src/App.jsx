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

      <div className="glass-panel" style={{ marginTop: '2rem', padding: '1.5rem', borderLeft: '4px solid #3b82f6', backgroundColor: 'rgba(59, 130, 246, 0.05)' }}>
        <h3 style={{ color: '#3b82f6', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          💡 Why do famous frameworks "Fail" this benchmark? Are they bad?
        </h3>
        <p style={{ color: 'var(--text-secondary)', lineHeight: '1.5', marginBottom: '1rem' }}>
          Absolutely not! Frameworks like <strong>Django, Laravel, and Express</strong> power some of the largest companies in the world (Instagram, Spotify, Netflix). The reason they "fail" our extreme Tier 4 stress test is because their default architectures (single-threaded Node.js, synchronous blocking Python/PHP workers) are not built to hold hundreds of long-lived, concurrent connections on a single machine out-of-the-box.
        </p>
        <p style={{ color: 'var(--text-secondary)', lineHeight: '1.5' }}>
          In the real world, big tech companies resolve this by spending heavily on <strong>Horizontal Scaling</strong> (hundreds of servers), Load Balancers, and advanced Caching. However, frameworks built with <strong>Rust (like Rullst) or Go</strong> utilize asynchronous event loops and micro-threads (goroutines) natively. This allows them to juggle thousands of connections simultaneously on a cheap, $5/month server with almost zero RAM penalty, resulting in significantly lower cloud costs and rock-solid resilience.
        </p>
      </div>

      <div className="framework-grid" style={{ marginTop: '3rem' }}>
        {results.map((fw, index) => (
          <FrameworkCard 
            key={fw.name}
            rank={index + 1}
            name={fw.name}
            language={fw.language}
            version={fw.version}
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
