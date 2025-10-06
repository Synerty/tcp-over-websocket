# TCP over WebSocket - Docker Setup

This directory contains Docker configuration files for running the TCP over WebSocket service.

## Architecture

The setup includes three services:

1. **Server** (`tcp-over-websocket-server`) - The WebSocket server that routes traffic between clients
2. **Client 1** (`tcp-over-websocket-client1`) - First client with `clientId: 1`
3. **Client 2** (`tcp-over-websocket-client2`) - Second client with `clientId: 2`

## Building Images

Run the build script to create all Docker images:

```bash
./docker/build.sh
```

This will create the following images:
- `tcp-over-websocket-base:latest` - Base image with application code
- `tcp-over-websocket-server:latest` - Server service
- `tcp-over-websocket-client1:latest` - Client 1 service  
- `tcp-over-websocket-client2:latest` - Client 2 service
- `tcp-over-websocket-tests:latest` - Test runner service

## Running Services

### Using Docker Compose (Recommended)

```bash
# Start all services
docker-compose -f docker/docker-compose.yml up

# Start in background
docker-compose -f docker/docker-compose.yml up -d

# Stop services
docker-compose -f docker/docker-compose.yml down

# Run tests (starts services and runs comprehensive tests)
docker-compose -f docker/docker-compose.yml --profile test up --build
```

### Using Docker Run Commands

```bash
# Start server
docker run -d --name tcp-server -p 38080:38080 -p 38001:38001 -p 38002:38002 tcp-over-websocket-server:latest

# Start client 1
docker run -d --name tcp-client1 -p 38011:38011 -p 38012:38012 tcp-over-websocket-client1:latest

# Start client 2  
docker run -d --name tcp-client2 -p 38031:38021 -p 38032:38022 tcp-over-websocket-client2:latest
```

## Port Configuration

- **Server**: 
  - 38080: WebSocket server port
  - 38001: server-to-client-tun1 tunnel (connects to tests on 39001/39003)
  - 38002: server-to-client-tun2 tunnel (connects to tests on 39002/39004)

- **Client 1**:
  - 38011: client-to-server-tun1 tunnel (connects to tests on 39011)
  - 38012: client-to-server-tun2 tunnel (connects to tests on 39012)

- **Client 2** (external ports mapped to avoid conflicts):
  - 38031: client-to-server-tun1 tunnel (connects to tests on 39011)
  - 38032: client-to-server-tun2 tunnel (connects to tests on 39012)

## Configuration

Each service uses its respective configuration from the `test_config` directory:
- Server: `test_config/websocket_server/config.json`
- Client 1: `test_config/websocket_client_1/config.json`  
- Client 2: `test_config/websocket_client_2/config.json`

## Testing

The Docker setup includes a comprehensive test suite that validates the TCP-over-WebSocket functionality:

```bash
# Run the complete test suite
docker-compose -f docker/docker-compose.yml --profile test up --build

# Run tests with verbose output
docker-compose -f docker/docker-compose.yml --profile test run --rm tests /app/run_tests.sh --verbose

# Run specific test suite
docker-compose -f docker/docker-compose.yml --profile test run --rm tests /app/run_tests.sh --suite data_transfer
```

Available test suites:
- `data_transfer` - Large data transfers with integrity validation
- `long_connections` - Sustained connections and throughput
- `failover` - High availability client switching
- `performance` - Latency, throughput, and memory benchmarks

Test results are saved to `./test-logs/` directory.

## High Availability

The setup supports high availability with two clients. When a TCP connection is made to either client, that client becomes "active" and receives all server-side connections. The other client's connections are terminated automatically.

## Updated Port Configuration

The tunnels are now configured as follows:
- **server-to-client-tun1**: binds on 38001, connects to tests on 39001 (client 1) or 39003 (client 2)
- **server-to-client-tun2**: binds on 38002, connects to tests on 39002 (client 1) or 39004 (client 2)
- **client-to-server-tun1**: binds on 38011/38021, connects to tests on 39011
- **client-to-server-tun2**: binds on 38012/38022, connects to tests on 39012

This configuration allows tests to verify which client is active by checking which test server ports receive connections:
- **Client 1 active**: Server tunnels connect to ports 39001, 39002
- **Client 2 active**: Server tunnels connect to ports 39003, 39004

## Logs

View logs for any service:

```bash
# Using docker-compose
docker-compose -f docker/docker-compose.yml logs server
docker-compose -f docker/docker-compose.yml logs client1
docker-compose -f docker/docker-compose.yml logs client2
docker-compose -f docker/docker-compose.yml --profile test logs tests

# Using docker run
docker logs tcp-server
docker logs tcp-client1
docker logs tcp-client2
```