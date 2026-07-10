#!/bin/bash

set -e

print_usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Run side-by-side comparison test of Prequal vs Round-Robin.

OPTIONS:
    -d, --duration SEC      Duration per load level (default: 120)
    -s, --step NUM          Run only a specific step from 1 to 9 (e.g. 1 for 75%)
    -h, --help             Show this help message

DESCRIPTION:
    Tests both algorithms simultaneously by running load against both
    load balancer instances (ports 8080 and 8081) in parallel.

    Ramps load from 75% to 174% of baseline capacity in multiplicative
    steps of 10/9, matching the methodology from Figure 6 in the paper.

    Load levels tested:
      75%, 83%, 93%, 103%, 114%, 127%, 141%, 157%, 174%

REQUIREMENTS:
    - hey must be installed: go install github.com/rakyll/hey@latest
    - Both load balancers must be running (docker-compose up)

EXAMPLE:
    ./compare.sh --duration 120

EOF
}

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

DURATION=120
STEP=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -d|--duration)
            DURATION="$2"
            shift 2
            ;;
        -s|--step)
            STEP="$2"
            shift 2
            ;;
        -h|--help)
            print_usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            print_usage
            exit 1
            ;;
    esac
done

check_hey
check_services

echo ""
echo "========================================="
echo "  Side-by-Side Algorithm Comparison"
echo "  Prequal (8080) vs Round-Robin (8081)"
echo "========================================="
echo "Duration per level: ${DURATION}s"
echo ""

mkdir -p metrics

echo "Determining baseline capacity..."
echo "Running calibration test (30s on Prequal)..."
BASELINE=$(hey -z 30s -q 100 http://localhost:8080 2>&1 | grep "Requests/sec:" | awk '{print $2}')
echo "Baseline capacity: ${BASELINE} req/sec"
echo ""
echo "Wait 30s to let the servers cool down"
sleep 30

LEVELS=(0.75 0.83 0.93 1.03 1.14 1.27 1.41 1.57 1.74)
LEVEL_NAMES=("75%" "83%" "93%" "103%" "114%" "127%" "141%" "157%" "174%")

for i in "${!LEVELS[@]}"; do
    if [ -n "$STEP" ] && [ "$((i+1))" -ne "$STEP" ]; then
        continue
    fi

    level=${LEVELS[$i]}
    name=${LEVEL_NAMES[$i]}
    qps=$(echo "$BASELINE * $level" | bc -l | awk '{printf "%.0f", $1}')

    echo "========================================="
    echo "Step $((i+1))/9: Load Level $name"
    echo "Target: ${qps} req/sec per algorithm"
    echo "========================================="
    echo "Calculated Target QPS: $qps"
    echo ""

    echo "1/2: Testing Round-Robin..."
    hey -z ${DURATION}s -q $qps http://localhost:8081 > ./metrics/rr_${i}.txt 2>&1

    echo "Waiting 5 seconds before switching..."
    sleep 5

    echo "2/2: Testing Prequal..."
    hey -z ${DURATION}s -q $qps http://localhost:8080 > ./metrics/prequal_${i}.txt 2>&1

    echo "Waiting 5 seconds before next level..."
    sleep 5

    echo ""
    echo "--- Round-Robin Results ---"
    grep -E "Requests/sec:|p50|p99|p99.9" ./metrics/rr_${i}.txt | head -5

    echo ""
    echo "--- Prequal Results ---"
    grep -E "Requests/sec:|p50|p99|p99.9" ./metrics/prequal_${i}.txt | head -5

    echo ""
    echo "Completed step $((i+1))/9"
    echo ""

    if [ $i -lt 8 ]; then
        echo "Pausing 10 seconds before next level..."
        sleep 10
    fi
done

echo ""
echo "========================================="
echo "         Test Complete"
echo "========================================="
echo ""
echo "View comparison in Grafana:"
echo "  http://localhost:3001"
echo ""
echo "Use the algorithm dropdown to filter or show both"
echo ""
echo "Detailed results saved in ./metrics/rr_*.txt and ./metrics/prequal_*.txt"
