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

# $1 = LB port, $2 = server id, $3 = backend address (host:port)
add_server() {
    curl -s -o /dev/null -w "%{http_code}" -X POST "http://localhost:$1/admin/servers" \
        -H "Content-Type: application/json" \
        -d "{\"id\":\"$2\",\"address\":\"$3\"}"
    echo " -> registered $2 ($3) on LB port $1"
}

# $1 = LB port, $2 = server id
remove_server() {
    curl -s -o /dev/null -w "%{http_code}" -X DELETE "http://localhost:$1/admin/servers?id=$2"
    echo " -> removed $2 from LB port $1"
}

DURATION=360
TARGET_LOAD=1.27

echo "========================================="
echo " Dynamic Experiment 2: Add 2 New Servers"
echo "========================================="

check_hey
check_services

mkdir -p metrics/dynamic

echo ""
echo "Determining baseline capacity..."
BASELINE=$(hey -z 30s -q 100 http://localhost:8080 2>&1 | grep "Requests/sec:" | awk '{print $2}')
QPS_TARGET=$(echo "$BASELINE * $TARGET_LOAD" | bc -l | awk '{printf "%.0f", $1}')
echo "QPS: ${QPS_TARGET} req/sec"

echo ""
echo "Making sure server4/server5 containers exist (but keeping them stopped for now)..."
docker compose --profile dynamic up -d --no-recreate server4 server5
docker stop server4 server5 > /dev/null 2>&1 || true

# ROUND ROBIN phase
echo ""
echo "=== ROUND ROBIN TEST (6 Minutes) ==="
hey -z ${DURATION}s -q $QPS_TARGET http://localhost:8081 > ./metrics/dynamic/rr_add2.txt 2>&1 &
PID_RR=$!

echo "Phase 1 (RR): 3 servers active. Waiting 2 minutes..."
sleep 120

echo "Phase 2 (RR): Starting server4/server5 and registering them with the RR load balancer..."
docker start server4 server5
sleep 3
add_server 8081 "server-3" "server4:80"
add_server 8081 "server-4" "server5:80"

echo "Phase 3 (RR): 5 servers active. Waiting for completion (4 minutes)..."
wait $PID_RR
echo "Round Robin completed!"

echo ""
echo "Resetting: removing server4/server5 from RR load balancer and stopping them..."
remove_server 8081 "server-3"
remove_server 8081 "server-4"
docker stop server4 server5
sleep 15

# PREQUAL phase
echo ""
echo "=== PREQUAL TEST (6 Minutes) ==="
hey -z ${DURATION}s -q $QPS_TARGET http://localhost:8080 > ./metrics/dynamic/pq_add2.txt 2>&1 &
PID_PQ=$!

echo "Phase 1 (PQ): 3 servers active. Waiting 2 minutes..."
sleep 120

echo "Phase 2 (PQ): Starting server4/server5 and registering them with the Prequal load balancer..."
docker start server4 server5
sleep 3
add_server 8080 "server-3" "server4:80"
add_server 8080 "server-4" "server5:80"

echo "Phase 3 (PQ): 5 servers active. Waiting for completion (4 minutes)..."
wait $PID_PQ
echo "Prequal completed!"

echo ""
echo "Cleaning up: removing server4/server5 from Prequal load balancer and stopping them..."
remove_server 8080 "server-3"
remove_server 8080 "server-4"
docker stop server4 server5

echo ""
echo "Dynamic Experiment 2 (Add 2 servers) Completed!"
echo "Results saved in ./metrics/dynamic/rr_add2.txt and ./metrics/dynamic/pq_add2.txt"