#!/bin/bash
set -e

echo "Waiting for services to be ready..."

waitForPort() {
    local host=$1
    local port=$2
    local timeout=60
    local count=0

    while ! nc -z $host $port 2>/dev/null
    do
        if [ $count -ge $timeout ]
        then
            echo "Timeout waiting for $host:$port"
            exit 1
        fi
        echo "Waiting for $host:$port... ($count/$timeout)"
        sleep 1
        count=$((count + 1))
    done
    echo "$host:$port is ready"
}

# Source configuration variables
source /app/extract_config_vars.sh /app/test_config

# Wait for server WebSocket port
waitForPort server $SERVER_WS_PORT

# Wait for server listen ports
for port in $SERVER_LISTEN_PORTS
do
    waitForPort server $port
done

# Wait for client1 listen ports
for port in $CLIENT1_LISTEN_PORTS
do
    waitForPort client1 $port
done

# Wait for client2 listen ports
for port in $CLIENT2_LISTEN_PORTS
do
    waitForPort client2 $port
done

echo "All services are ready."

echo "Starting test servers for connect-to ports..."

# Start background netcat listeners for all connect-to ports
for port in $ALL_CONNECT_PORTS
do
    echo "Starting test server on port $port"
    nc -l -p $port &
done

echo "Starting tests..."
sleep 5

# Run the tests using pytest directly
cd /app/tests

# Build pytest arguments based on provided arguments
PYTEST_ARGS="-v --asyncio-mode=auto --tb=short -ra --maxfail=5"

# Only add additional arguments if they are provided and not empty
if [ $# -gt 0 ] && [ -n "$1" ]
then
    PYTEST_ARGS="$PYTEST_ARGS $@"
fi

pytest $PYTEST_ARGS

# Capture the exit code
TEST_EXIT_CODE=$?

# Kill background processes
jobs -p | xargs -r kill

# Exit with the test exit code
exit $TEST_EXIT_CODE