const fs = require('fs');

const data = JSON.parse(fs.readFileSync('dashboard/src/data.json', 'utf8'));

// Calculate Efficiency
data.forEach(fw => {
  let ramMB = 1;
  if (fw.peakRam.includes("MiB")) ramMB = parseFloat(fw.peakRam);
  if (fw.peakRam.includes("GiB")) ramMB = parseFloat(fw.peakRam) * 1024;
  if (ramMB === 0 || isNaN(ramMB)) ramMB = 9999;
  fw.efficiencyScore = Math.round(fw.jsonRps / ramMB);
});

// Sort by Efficiency descending
data.sort((a, b) => b.efficiencyScore - a.efficiencyScore);

let md = `# 🏆 Rullst Benchmarks 2026: The Ultimate Results

> **Last Updated:** June 22, 2026
> **Interactive Dashboard:** [View Web Dashboard](https://your-github-username.github.io/Benchmarks/)

Welcome to the consolidated, high-performance benchmarking results. We pit **23 modern web frameworks** against each other in a rigorous, containerized 4-tier stress test.

## 🎯 The Ultimate Ranking (By Efficiency)

In modern cloud environments, pure speed means nothing if it costs thousands of dollars in RAM. The ranking below is sorted by the **Efficiency Score** (JSON Requests Per Second divided by Peak RAM usage). 

*The higher the score, the more performant and cheaper the framework is to host.*

| 🏆 Rank | Framework | Language | Efficiency (RPS/MB) | JSON RPS | DB Single RPS | Avg Latency | Peak RAM | Status |
|:---:|---|---|---:|---:|---:|---:|---:|:---:|
`;

data.forEach((fw, index) => {
  let rankIcon = `${index + 1}`;
  if (index === 0) rankIcon = '🥇 1st';
  if (index === 1) rankIcon = '🥈 2nd';
  if (index === 2) rankIcon = '🥉 3rd';
  
  let fwName = fw.name === 'Rullst' ? `**${fw.name}** 👑` : fw.name;
  let statusIcon = fw.status === 'Passed' ? '✅ Passed' : '❌ Failed';

  md += `| ${rankIcon} | ${fwName} | ${fw.language} | **${fw.efficiencyScore.toLocaleString()}** | ${fw.jsonRps.toLocaleString()} | ${fw.dbRps.toLocaleString()} | ${fw.latency} | ${fw.peakRam} | ${statusIcon} |\n`;
});

md += `

---

## 📈 Methodology Explained

If you want to understand the Tiers (Tier 1 to 4) and how we measure database throughput, latency, and idle resources, please refer to the detailed methodology in our [README.md](./README.md).

*Generated automatically by the Rullst Benchmark Suite.*
`;

fs.writeFileSync('benchmarks_results.md', md);
console.log('benchmarks_results.md updated successfully.');
