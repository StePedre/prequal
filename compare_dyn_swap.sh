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

# $1 = LB port. Simultaneous swap: server1 (server-0) out, server6 (server-6) in.
swap_server1_for_server6() {
    local port=$1

    echo "Pre-warming server6 (starting container, waiting for health probe)..."
    docker start server6
    sleep 2

    echo "Swap instant on LB port $port: registering server6 / removing server1 in parallel..."
    add_server "$port" "server-6" "server6:80" &
    PID_ADD=$!
    remove_server "$port" "server-0" &
    PID_DEL=$!
    wait $PID_ADD $PID_DEL

    docker stop server1
}

# $1 = LB port. Restore original topology before next phase.
restore_server1() {
    local port=$1

    echo "Restoring original topology on LB port $port: server1 back in, server6 out..."
    docker start server1
    sleep 2

    add_server "$port" "server-0" "server1:80" &
    PID_ADD=$!
    remove_server "$port" "server-6" &
    PID_DEL=$!
    wait $PID_ADD $PID_DEL

    docker stop server6
    sleep 15
}

DURATION=360
TARGET_LOAD=1.27

echo "========================================="
echo " Dynamic Experiment 3: Simultaneous Swap"
echo " server1 (out) <-> server6 (in), both contended"
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
echo "Making sure server6 container exists (but keeping it stopped for now)..."
docker compose --profile dynamic up -d --no-recreate server6
docker stop server6 > /dev/null 2>&1 || true

# ROUND ROBIN phase
echo ""
echo "=== ROUND ROBIN TEST (6 Minutes) ==="
hey -z ${DURATION}s -q $QPS_TARGET http://localhost:8081 > ./metrics/dynamic/rr_swap.txt 2>&1 &
PID_RR=$!

echo "Phase 1 (RR): original topology (server1, server2, server3). Waiting 2 minutes..."
sleep 120

echo "Phase 2 (RR): simultaneous swap server1 -> server6..."
swap_server1_for_server6 8081

echo "Phase 3 (RR): swapped topology (server6, server2, server3). Waiting for completion (4 minutes)..."
wait $PID_RR
echo "Round Robin completed!"

restore_server1 8081

# PREQUAL phase
echo ""
echo "=== PREQUAL TEST (6 Minutes) ==="
hey -z ${DURATION}s -q $QPS_TARGET http://localhost:8080 > ./metrics/dynamic/pq_swap.txt 2>&1 &
PID_PQ=$!

echo "Phase 1 (PQ): original topology (server1, server2, server3). Waiting 2 minutes..."
sleep 120

echo "Phase 2 (PQ): simultaneous swap server1 -> server6..."
swap_server1_for_server6 8080

echo "Phase 3 (PQ): swapped topology (server6, server2, server3). Waiting for completion (4 minutes)..."
wait $PID_PQ
echo "Prequal completed!"

restore_server1 8080

echo ""
echo "Dynamic Experiment 3 (Simultaneous Swap) Completed!"
echo "Results saved in ./metrics/dynamic/rr_swap.txt and ./metrics/dynamic/pq_swap.txt"