import React, { useState, useEffect } from 'react';
import { FrameworkCard } from './components/FrameworkCard';
import { RullstAnalysis } from './components/RullstAnalysis';
import resultsData from './data.json';

function App() {
  const [results, setResults] = useState([]);

  useEffect(() => {
    // Sort by Text RPS descending
    const sorted = [...resultsData].sort((a, b) => b.textRps - a.textRps);
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

      <div className="framework-grid">
        {results.map((fw, index) => (
          <FrameworkCard 
            key={fw.name}
            name={fw.name}
            language={fw.language}
            textRps={fw.textRps}
            dbRps={fw.dbRps}
            stars={fw.stars}
            highlight={fw.highlight}
          />
        ))}
      </div>

      <RullstAnalysis />
    </div>
  );
}

export default App;
