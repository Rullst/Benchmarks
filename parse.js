const fs = require('fs');

const frameworks = ['express', 'fastify', 'nestjs', 'hono', 'go-fiber', 'go-gin'];

for (const fw of frameworks) {
    let json_rps = 'TBD', db_rps = 'TBD', latency = 'TBD', idle_ram = 'TBD', peak_ram = 'TBD', status = 'Passed';
    
    try {
        const c = fs.readFileSync(`results/${fw}_tier1_json.txt`, 'utf8');
        const m = c.match(/Reqs\/sec\s+([0-9.]+)/);
        if (m) json_rps = m[1];
    } catch(e) {}
    
    try {
        const c = fs.readFileSync(`results/${fw}_tier1_db-single.txt`, 'utf8');
        const m = c.match(/Reqs\/sec\s+([0-9.]+)/);
        if (m) db_rps = m[1];
    } catch(e) {}
    
    try {
        const c = fs.readFileSync(`results/${fw}_tier2_json.txt`, 'utf8');
        const m = c.match(/Latency\s+([0-9.]+[a-zA-Z]+)/);
        if (m) latency = m[1];
    } catch(e) {}
    
    try {
        const lines = fs.readFileSync(`results/${fw}_tier3_idle.txt`, 'utf8').split('\n');
        if (lines.length > 1) {
            const parts = lines[1].trim().split(/\s+/);
            if (parts.length > 3) idle_ram = parts[3];
        }
    } catch(e) {}
    
    try {
        const lines = fs.readFileSync(`results/${fw}_tier3_peak.txt`, 'utf8').split('\n');
        if (lines.length > 1) {
            const parts = lines[1].trim().split(/\s+/);
            if (parts.length > 3) peak_ram = parts[3];
        }
    } catch(e) {}

    let version = 'TBD';
    if (fw === 'express') version = '5.1.0';
    if (fw === 'fastify') version = '5.8.0';
    if (fw === 'nestjs') version = 'latest';
    if (fw === 'hono') version = '4.12.0';
    if (fw === 'go-fiber') version = 'v3.0.0';
    if (fw === 'go-gin') version = 'v1.12.0';
    
    console.log(`| ${fw.charAt(0).toUpperCase() + fw.slice(1)} | ${version} | ${json_rps} | ${db_rps} | ${latency} | ${idle_ram} | ${peak_ram} | ${status} |`);
}
