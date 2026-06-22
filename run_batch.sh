#!/bin/bash
set -e

if [ "$#" -eq 0 ]; then
    echo "Usage: $0 <framework1> <framework2> ..."
    exit 1
fi

FRAMEWORKS=("$@")
mkdir -p results

echo "=========================================================="
echo " Starting Benchmarks for: ${FRAMEWORKS[*]}"
echo "=========================================================="

for FRAMEWORK in "${FRAMEWORKS[@]}"; do
    echo ""
    echo "----------------------------------------------------------"
    echo " [1/4] Building and starting $FRAMEWORK..."
    echo "----------------------------------------------------------"
    
    # 1. Start the DB and the framework
    docker compose up -d --build db $FRAMEWORK
    echo "Waiting 20s for $FRAMEWORK to fully start..."
    sleep 20
    
    # We need to know which port the framework uses from docker-compose
    # A robust way is to just grep docker-compose or assume ports based on a list.
    # But wait, we can just use the mapped port from docker-compose!
    # Let's extract the port using docker compose port
    PORT=$(docker compose port $FRAMEWORK 3000 | cut -d ':' -f 2 || echo "8000")
    if [ -z "$PORT" ] || [ "$PORT" == "8000" ]; then
        # Fallback to hardcoded mapping or grep if docker compose port fails
        PORT=$(grep -A 15 " $FRAMEWORK:" docker-compose.yml | grep "-" | grep ":" | grep 3000 | head -1 | awk -F'"' '{print $2}' | cut -d':' -f1 || echo "8000")
        if [ -z "$PORT" ]; then PORT=8000; fi
    fi
    echo "Detected $FRAMEWORK running on port $PORT"

    echo ""
    echo "----------------------------------------------------------"
    echo " [2/4] TIER 1: Fast Load (125 conn, 10s)"
    echo "----------------------------------------------------------"
    for endpoint in "text" "json" "db-single" "html"; do
        echo "> Benchmarking /$endpoint..."
        docker run --rm --network host alpine/bombardier -c 125 -d 10s "http://127.0.0.1:$PORT/$endpoint" > "results/${FRAMEWORK}_tier1_${endpoint}.txt" || echo "Failed $endpoint"
    done

    echo ""
    echo "----------------------------------------------------------"
    echo " [3/4] TIER 2: Concurrency & Latency (300 conn, 30s)"
    echo "----------------------------------------------------------"
    # We just test JSON for high concurrency
    echo "> Benchmarking /json with high concurrency..."
    docker run --rm --network host alpine/bombardier -c 300 -d 30s "http://127.0.0.1:$PORT/json" > "results/${FRAMEWORK}_tier2_json.txt" || echo "Failed json"

    echo ""
    echo "----------------------------------------------------------"
    echo " [4/4] TIER 3: Resource Efficiency (Idle vs Peak)"
    echo "----------------------------------------------------------"
    echo "> Capturing Idle Stats (10s)..."
    docker stats --no-stream "benchmarks-$FRAMEWORK-1" > "results/${FRAMEWORK}_tier3_idle.txt" || echo "Failed idle stats"
    
    echo "> Applying 200 conn load for 30s to capture Peak Stats..."
    docker run --rm --network host alpine/bombardier -c 200 -d 30s "http://127.0.0.1:$PORT/json" > /dev/null &
    BOMB_PID=$!
    sleep 15
    docker stats --no-stream "benchmarks-$FRAMEWORK-1" > "results/${FRAMEWORK}_tier3_peak.txt" || echo "Failed peak stats"
    wait $BOMB_PID || true

    echo ""
    echo "----------------------------------------------------------"
    echo " [5/4] TIER 4: Stress / Resilience (500 conn, 2m)"
    echo "----------------------------------------------------------"
    echo "> Stress testing /json for 2 minutes..."
    docker run --rm --network host alpine/bombardier -c 500 -d 2m "http://127.0.0.1:$PORT/json" > "results/${FRAMEWORK}_tier4_json.txt" || echo "Failed stress test"

    echo ""
    echo "----------------------------------------------------------"
    echo " Cleaning up $FRAMEWORK..."
    echo "----------------------------------------------------------"
    docker compose stop $FRAMEWORK
    docker compose rm -f $FRAMEWORK
done

echo ""
echo "=========================================================="
echo " All Benchmarks Finished for: ${FRAMEWORKS[*]}"
echo "=========================================================="
