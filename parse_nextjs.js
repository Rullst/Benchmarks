const fs = require('fs');

const fws = [
    { id: 'nextjs', name: 'Next.js', version: '15.5.x' }
];

console.log('| Framework | Version | Tier 1 (JSON RPS) | Tier 1 (DB RPS) | Tier 2 (Avg Latency) | Tier 3 (Idle RAM) | Tier 3 (Peak RAM) | Tier 4 (Status) |');
console.log('|-----------|---------|-------------------|-----------------|----------------------|-------------------|-------------------|-----------------|');

for (const fw of fws) {
    let json_rps = 'N/A', db_rps = 'N/A', avg_lat = 'N/A', idle_ram = 'N/A', peak_ram = 'N/A', status = 'Failed';

    try {
        const lines = fs.readFileSync(`results/${fw.id}_tier1_json.txt`, 'utf8').split('\n');
        for (let line of lines) {
            if (line.includes('Reqs/sec')) {
                json_rps = line.trim().split(/\s+/)[1];
            }
        }
    } catch(e) {}

    try {
        const lines = fs.readFileSync(`results/${fw.id}_tier1_db-single.txt`, 'utf8').split('\n');
        for (let line of lines) {
            if (line.includes('Reqs/sec')) {
                db_rps = line.trim().split(/\s+/)[1];
            }
        }
    } catch(e) {}

    try {
        const lines = fs.readFileSync(`results/${fw.id}_tier2_json.txt`, 'utf8').split('\n');
        for (let line of lines) {
            if (line.includes('Latency')) {
                avg_lat = line.trim().split(/\s+/)[1];
            }
        }
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

    try {
        const content = fs.readFileSync(`results/${fw.id}_tier4_stress.txt`, 'utf8');
        if (content.includes('Done!')) {
            status = 'Passed';
        }
    } catch(e) {}

    console.log(`| ${fw.name} | ${fw.version} | ${json_rps} | ${db_rps} | ${avg_lat} | ${idle_ram} | ${peak_ram} | ${status} |`);
}
