#!/bin/bash

set -e

check_hey() {
    if ! command -v hey &> /dev/null; then
        echo "Error: hey is not installed"
        echo "Install with: go install github.com/rakyll/hey@latest"
        exit 1
    fi
}

check_services() {
    echo "Checking services..."
    if ! curl -s http://localhost:8080/health > /dev/null 2>&1; then
        echo "Error: Prequal load balancer not responding on port 8080"
        echo "Start services with: docker-compose up -d"
        exit 1
    fi
    if ! curl -s http://localhost:8081/health > /dev/null 2>&1; then
        echo "Error: Round-Robin load balancer not responding on port 8081"
        echo "Start services with: docker-compose up -d"
        exit 1
    fi
    echo "Both load balancers are running"
}

DURATION=360
TARGET_LOAD=1.27

echo "========================================="
echo " Dynamic Experiment 1: Server Kill"
echo "========================================="

mkdir -p metrics/dynamic

echo "Determining baseline capacity..."
BASELINE=$(hey -z 30s -q 100 http://localhost:8080 2>&1 | grep "Requests/sec:" | awk '{print $2}')

# ROUND ROBIN phase
echo ""
echo "=== ROUND ROBIN TEST (6 Minutes) ==="
QPS_TARGET=$(echo "$BASELINE * $TARGET_LOAD" | bc -l | awk '{printf "%.0f", $1}')
echo "QPS: ${QPS_TARGET} req/sec"

hey -z ${DURATION}s -q $QPS_TARGET http://localhost:8081 > ./metrics/dynamic/rr_dyn_k1.txt 2>&1 &
PID_RR=$!

echo "Phase 1 (RR): 3 servers active. Waiting 2 minutes..."
sleep 120

echo "Phase 2 (RR): Killing server1..."
docker stop server1

echo "Phase 3 (RR): 2 servers active. Waiting for completion (4 minutes)..."
wait $PID_RR
echo "Round Robin completed!"

# --- RESET environment ---
echo ""
docker restart server1 server2 server3
sleep 15

# PREQUAL phase
echo ""
echo "=== PREQUAL TEST (6 Minutes) ==="
hey -z ${DURATION}s -q $QPS_TARGET http://localhost:8080 > ./metrics/dynamic/pq_dyn_k1.txt 2>&1 &
PID_PQ=$!

echo "Phase 1 (PQ): 3 servers active. Waiting 2 minutes..."
sleep 120

echo "Phase 2 (PQ): Killing server1..."
docker stop server1

echo "Phase 3 (PQ): 2 servers active. Waiting for completion (4 minutes)..."
wait $PID_PQ
echo "Prequal completed!"

echo ""
echo "Dynamic Experiment 1 Completed!"
echo "Remember to run 'docker start server1' before the next experiment."
