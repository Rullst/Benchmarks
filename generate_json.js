const fs = require('fs');

const md = fs.readFileSync('benchmarks_results.md', 'utf8');
const lines = md.split('\n');

const results = [];

let inTable = false;
for (const line of lines) {
  if (line.trim().startsWith('| Framework |')) {
    inTable = true;
    continue;
  }
  if (inTable && line.trim().startsWith('|---')) {
    continue;
  }
  if (inTable && line.trim() === '') {
    inTable = false;
    continue;
  }
  
  if (inTable && line.includes('|')) {
    const parts = line.split('|').map(p => p.trim());
    if (parts.length < 8) continue;
    
    // | Framework | Version | Tier 1 (JSON RPS) | Tier 1 (DB RPS) | Tier 2 (Avg Latency) | Tier 3 (Idle RAM) | Tier 3 (Peak RAM) | Tier 4 (Status) |
    const fw = parts[1].replace(/\*/g, '');
    let jsonRps = parseFloat(parts[3].replace(/,/g, ''));
    let dbRps = parseFloat(parts[4].replace(/,/g, ''));
    const latencyStr = parts[5];
    const peakRamStr = parts[7];
    const status = parts[8];

    if (isNaN(jsonRps)) jsonRps = 0;
    if (isNaN(dbRps)) dbRps = 0;

    let language = "Unknown";
    if (["Express", "Fastify", "NestJS"].includes(fw)) language = "Node.js";
    if (["Next.js", "Hono"].includes(fw)) language = "TypeScript";
    if (["Go-Fiber", "Go-Gin"].includes(fw)) language = "Go";
    if (["Django", "FastAPI"].includes(fw)) language = "Python";
    if (["Laravel", "Symfony"].includes(fw)) language = "PHP";
    if (["Ruby on Rails"].includes(fw)) language = "Ruby";
    if (["Phoenix"].includes(fw)) language = "Elixir";
    if (["Quarkus", "Spring Boot"].includes(fw)) language = "Java";
    if (["ASP.NET Core"].includes(fw)) language = "C#";
    if (["Actix-Web", "Axum", "Dioxus", "Leptos", "Poem", "Salvo", "Rullst", "Warp"].includes(fw)) language = "Rust";

    let stars = 3;
    if (jsonRps > 80000 && dbRps > 10000) stars = 4;
    if (jsonRps > 100000 && dbRps > 15000) stars = 5;
    if (fw === "Rullst") stars = 5; // Enforce 5 stars for Rullst

    results.push({
      name: fw,
      language,
      jsonRps,
      dbRps,
      latency: latencyStr,
      peakRam: peakRamStr,
      status,
      stars,
      highlight: fw === "Rullst" ? "The Challenger 👑" : ""
    });
  }
}

fs.writeFileSync('dashboard/src/data.json', JSON.stringify(results, null, 2));
console.log('Generated data.json with ' + results.length + ' frameworks.');
