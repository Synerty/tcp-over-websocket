#!/usr/bin/env bash

set -o nounset
set -o errexit

rm -rf test-logs
mkdir -p test-logs

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "Building TCP over WebSocket Docker images..."
echo "Project root: $PROJECT_ROOT"

# Change to project root directory
cd "$PROJECT_ROOT"

# Source configuration variables
source docker/scripts/extract_config_vars.sh test_config

# Create temporary directory for modified Dockerfiles
TEMP_DIR=$(mktemp -d)
trap "rm -rf $TEMP_DIR" EXIT

# Function to create modified Dockerfile with dynamic EXPOSE
createModifiedDockerfile() {
    local original_dockerfile=$1
    local temp_dockerfile=$2
    local expose_ports=$3
    
    # Copy original dockerfile and replace EXPOSE line
    sed '/^EXPOSE /d' "$original_dockerfile" > "$temp_dockerfile"
    
    # Add new EXPOSE line before CMD
    sed -i '/^CMD /i\EXPOSE '"$expose_ports" "$temp_dockerfile"
}

# Build base image first
echo "Building base image..."
docker build -f docker/Dockerfile.base -t tcp-over-websocket-base:latest .

# Build test base image
echo "Building test base image..."
docker build -f docker/Dockerfile.test-base -t tcp-over-websocket-test-base:latest .

# Build server image with dynamic ports
echo "Building server image..."
SERVER_EXPOSE_PORTS="$SERVER_WS_PORT $SERVER_LISTEN_PORTS"
createModifiedDockerfile "docker/Dockerfile.server" "$TEMP_DIR/Dockerfile.server" "$SERVER_EXPOSE_PORTS"
docker build --no-cache -f "$TEMP_DIR/Dockerfile.server" -t tcp-over-websocket-server:latest .

# Build client 1 image with dynamic ports
echo "Building client 1 image..."
createModifiedDockerfile "docker/Dockerfile.client1" "$TEMP_DIR/Dockerfile.client1" "$CLIENT1_LISTEN_PORTS"
docker build --no-cache -f "$TEMP_DIR/Dockerfile.client1" -t tcp-over-websocket-client1:latest .

# Build client 2 image with dynamic ports
echo "Building client 2 image..."
createModifiedDockerfile "docker/Dockerfile.client2" "$TEMP_DIR/Dockerfile.client2" "$CLIENT2_LISTEN_PORTS"
docker build --no-cache -f "$TEMP_DIR/Dockerfile.client2" -t tcp-over-websocket-client2:latest .

# Build test image with dynamic ports
echo "Building test image..."
createModifiedDockerfile "docker/Dockerfile.tests" "$TEMP_DIR/Dockerfile.tests" "$ALL_CONNECT_PORTS"
docker build --no-cache -f "$TEMP_DIR/Dockerfile.tests" -t tcp-over-websocket-tests:latest .

echo "All Docker images built successfully!"
echo ""
echo "Available images:"
docker images | grep tcp-over-websocket

echo ""
echo "To run the services:"
echo "  Server:   docker run -p $SERVER_WS_PORT:$SERVER_WS_PORT $(echo $SERVER_LISTEN_PORTS | sed 's/\([0-9]\+\)/-p \1:\1/g') tcp-over-websocket-server:latest"
echo "  Client 1: docker run $(echo $CLIENT1_LISTEN_PORTS | sed 's/\([0-9]\+\)/-p \1:\1/g') tcp-over-websocket-client1:latest"
echo "  Client 2: docker run $(echo $CLIENT2_LISTEN_PORTS | sed 's/\([0-9]\+\)/-p \1:\1/g') tcp-over-websocket-client2:latest"
echo ""
echo "Or use docker-compose:"
echo "  # Start services:"
echo "  docker-compose -f docker/docker-compose.yml up"
echo ""
echo "  # Run tests (starts services and runs tests):"
echo "  docker-compose -f docker/docker-compose.yml --profile test up --build"