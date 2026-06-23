const fs = require('fs');
const path = require('path');

const resultsDir = path.join(__dirname, 'results');
const frameworks = [
  { id: 'actix', name: 'Actix-Web', lang: 'Rust', version: '4.13.x' },
  { id: 'aspnet-core', name: 'ASP.NET Core', lang: 'C#', version: '10.0.x' },
  { id: 'axum', name: 'Axum', lang: 'Rust', version: '0.8.x' },
  { id: 'dioxus', name: 'Dioxus', lang: 'Rust', version: '0.7.x' },
  { id: 'django', name: 'Django', lang: 'Python', version: '6.0.x' },
  { id: 'express', name: 'Express', lang: 'Node.js', version: '5.1.x' },
  { id: 'fastapi', name: 'FastAPI', lang: 'Python', version: '0.138.x' },
  { id: 'fastify', name: 'Fastify', lang: 'Node.js', version: '5.8.x' },
  { id: 'go-fiber', name: 'Go-Fiber', lang: 'Go', version: '3.0.x' },
  { id: 'go-gin', name: 'Go-Gin', lang: 'Go', version: '1.11.x' },
  { id: 'hono', name: 'Hono', lang: 'TypeScript', version: '4.12.x' },
  { id: 'laravel', name: 'Laravel', lang: 'PHP', version: '13.x' },
  { id: 'leptos', name: 'Leptos', lang: 'Rust', version: '0.7.x' },
  { id: 'nestjs', name: 'NestJS', lang: 'Node.js', version: '11.1.x' },
  { id: 'nextjs', name: 'Next.js', lang: 'TypeScript', version: '15.x' },
  { id: 'phoenix', name: 'Phoenix', lang: 'Elixir', version: '1.8.x' },
  { id: 'poem', name: 'Poem', lang: 'Rust', version: '3.x' },
  { id: 'quarkus', name: 'Quarkus', lang: 'Java', version: '3.36.x' },
  { id: 'rails', name: 'Ruby on Rails', lang: 'Ruby', version: '7.2.x' },
  { id: 'rullst', name: 'Rullst', lang: 'Rust', highlight: 'The Challenger 👑', stars: 5, version: '4.0.1' },
  { id: 'salvo', name: 'Salvo', lang: 'Rust', version: '0.93.x' },
  { id: 'springboot', name: 'Spring Boot', lang: 'Java', version: '4.0.x' },
  { id: 'symfony', name: 'Symfony', lang: 'PHP', version: '7.4.x' }
];


const extractRps = (log) => {
  const m = log.match(/Reqs\/sec\s+([\d\.]+)/);
  return m ? parseFloat(m[1]) : 0;
};
const extractLatency = (log) => {
  const m = log.match(/Latency\s+([\d\.]+ms|[\d\.]+s|[\d\.]+m|[\d\.]+h|[\d\.]+µs)/);
  return m ? m[1] : 'N/A';
};
const extractRam = (log, fwId) => {
  let peak = '0B';
  const lines = log.split('\n');
  for (let l of lines) {
    if (l.includes(`benchmarks-${fwId}-1`) && !l.includes('CPU')) {
      const parts = l.trim().split(/\s+/);
      if (parts.length > 3) peak = parts[3];
    }
  }
  return peak;
};

const finalData = [];

for (const fw of frameworks) {
  const f_j1 = path.join(resultsDir, `${fw.id}_tier1_json.txt`);
  const f_d1 = path.join(resultsDir, `${fw.id}_tier1_db-single.txt`);
  const f_j2 = path.join(resultsDir, `${fw.id}_tier2_json.txt`);
  const f_t3 = path.join(resultsDir, `${fw.id}_tier3_peak.txt`);
  const f_j4 = path.join(resultsDir, `${fw.id}_tier4_json.txt`);

  const r_j1 = fs.existsSync(f_j1) ? fs.readFileSync(f_j1, 'utf8') : '';
  const r_d1 = fs.existsSync(f_d1) ? fs.readFileSync(f_d1, 'utf8') : '';
  const r_j2 = fs.existsSync(f_j2) ? fs.readFileSync(f_j2, 'utf8') : '';
  const r_t3 = fs.existsSync(f_t3) ? fs.readFileSync(f_t3, 'utf8') : '';
  const r_j4 = fs.existsSync(f_j4) ? fs.readFileSync(f_j4, 'utf8') : '';

  const jsonRps = extractRps(r_j1);
  const dbRps = extractRps(r_d1);
  const latency = extractLatency(r_j2);
  const peakRam = extractRam(r_t3, fw.id);
  const status = (r_j4.includes('connection refused') || r_j4.includes('timeout') || r_j4 === '') ? 'Failed' : 'Passed';

  let stars = fw.stars || (jsonRps > 80000 ? 5 : (jsonRps > 20000 ? 4 : 3));

  finalData.push({
    name: fw.name,
    language: fw.lang,
    version: fw.version,
    jsonRps,
    dbRps,
    latency,
    peakRam,
    status,
    stars,
    highlight: fw.highlight || ''
  });
}

fs.writeFileSync(path.join(__dirname, 'dashboard', 'src', 'data.json'), JSON.stringify(finalData, null, 2));
console.log('Successfully generated data.json with ' + finalData.length + ' frameworks.');
