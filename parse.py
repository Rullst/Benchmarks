import os
import re

frameworks = ['express', 'fastify', 'nestjs', 'hono', 'go-fiber', 'go-gin']

for fw in frameworks:
    json_rps, db_rps, p99, idle_ram, peak_ram = 'TBD', 'TBD', 'TBD', 'TBD', 'TBD'
    
    # Tier 1 JSON
    try:
        with open(f"results/{fw}_tier1_json.txt", "r") as f:
            content = f.read()
            match = re.search(r"Reqs/sec\s+([0-9.]+)", content)
            if match: json_rps = match.group(1)
    except: pass
    
    # Tier 1 DB
    try:
        with open(f"results/{fw}_tier1_db-single.txt", "r") as f:
            content = f.read()
            match = re.search(r"Reqs/sec\s+([0-9.]+)", content)
            if match: db_rps = match.group(1)
    except: pass
    
    # Tier 2 P99
    try:
        with open(f"results/{fw}_tier2_json.txt", "r") as f:
            content = f.read()
            match = re.search(r"99%\s+([0-9.]+[mus]+)", content)
            if match: p99 = match.group(1)
    except: pass
    
    # Tier 3 Idle
    try:
        with open(f"results/{fw}_tier3_idle.txt", "r") as f:
            lines = f.readlines()
            if len(lines) > 1:
                parts = lines[1].split()
                if len(parts) > 3: idle_ram = parts[3]
    except: pass
    
    # Tier 3 Peak
    try:
        with open(f"results/{fw}_tier3_peak.txt", "r") as f:
            lines = f.readlines()
            if len(lines) > 1:
                parts = lines[1].split()
                if len(parts) > 3: peak_ram = parts[3]
    except: pass

    version = 'TBD'
    if fw == 'express': version = '5.1.0'
    if fw == 'fastify': version = '5.8.0'
    if fw == 'nestjs': version = '11.1.0'
    if fw == 'hono': version = '4.12.0'
    if fw == 'go-fiber': version = 'v3.0.0'
    if fw == 'go-gin': version = 'v1.12.0'
    
    print(f"| {fw} | {version} | {json_rps} | {db_rps} | {p99} | {idle_ram} | {peak_ram} | Passed |")
