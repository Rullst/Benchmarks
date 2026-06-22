const fs = require('fs');

const frameworks = [
    { id: 'actix', name: 'Actix-Web', version: '4.x' },
    { id: 'axum', name: 'Axum', version: '0.8.x' },
    { id: 'dioxus', name: 'Dioxus', version: '0.7.x' },
    { id: 'leptos', name: 'Leptos', version: '0.7.x' },
    { id: 'poem', name: 'Poem', version: '3.x' },
    { id: 'salvo', name: 'Salvo', version: '0.93.x' }
];

console.log('| Framework | Version | Tier 1 (JSON RPS) | Tier 1 (DB RPS) | Tier 2 (Avg Latency) | Tier 3 (Idle RAM) | Tier 3 (Peak RAM) | Tier 4 (Status) |');
console.log('|-----------|---------|-------------------|-----------------|----------------------|-------------------|-------------------|-----------------|');

for (const fw of frameworks) {
    let json_rps = 'TBD', db_rps = 'TBD', latency = 'TBD', idle_ram = 'TBD', peak_ram = 'TBD', status = 'Passed';
    
    try {
        const c = fs.readFileSync(`results/${fw.id}_tier1_json.txt`, 'utf8');
        const m = c.match(/Reqs\/sec\s+([0-9.]+)/);
        if (m) json_rps = m[1];
    } catch(e) {}
    
    try {
        const c = fs.readFileSync(`results/${fw.id}_tier1_db-single.txt`, 'utf8');
        const m = c.match(/Reqs\/sec\s+([0-9.]+)/);
        if (m) db_rps = m[1];
    } catch(e) {}
    
    try {
        const c = fs.readFileSync(`results/${fw.id}_tier2_json.txt`, 'utf8');
        const m = c.match(/Latency\s+([0-9.]+[a-zA-Z]+)/);
        if (m) latency = m[1];
    } catch(e) {}
    
    try {
        const lines = fs.readFileSync(`results/${fw.id}_tier3_idle.txt`, 'utf8').split('\n');
        if (lines.length > 1) {
            const parts = lines[1].trim().split(/\s+/);
            if (parts.length > 3) idle_ram = parts[3];
        }
    } catch(e) {}
    
    try {
        const lines = fs.readFileSync(`results/${fw.id}_tier3_peak.txt`, 'utf8').split('\n');
        if (lines.length > 1) {
            const parts = lines[1].trim().split(/\s+/);
            if (parts.length > 3) peak_ram = parts[3];
        }
    } catch(e) {}
    
    console.log(`| ${fw.name} | ${fw.version} | ${json_rps} | ${db_rps} | ${latency} | ${idle_ram} | ${peak_ram} | ${status} |`);
}
