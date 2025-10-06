# TCP over WebSocket

```
┌───────────────────────────────────────────────────────────────────────────────┐
│                          TCP-over-WebSocket Architecture                      │
└───────────────────────────────────────────────────────────────────────────────┘

┌────────────────┐ ┌─────────────────┐      ┌────────────────┐ ┌────────────────┐
│  External XC1  │ │  External XC2   │      │  External XC3  │ │  External XC4  │
│    Site A      │ │    Site A       │      │    Site B      │ │    Site B      │
└────────────────┘ └─────────────────┘      └────────────────┘ └────────────────┘
   send/receive       send/receive              send/receive      send/receive
        │                  ▲                         │                ▲
        ▼                  │                         ▼                │
   ---------------------------- Client Services ------------------------------
┌────────────────┐ ┌─────────────────┐      ┌────────────────┐ ┌────────────────┐
│    Tunnel 1    │ │    Tunnel 2     │      │    Tunnel 1    │ │    Tunnel 2    │
│     Listen     │ │     Connect     │      │     Listen     │ │     Connect    │
│     Socket     │ │     Socket      │      │     Socket     │ │     Socket     │
└────────────────┘ └─────────────────┘      └────────────────┘ └────────────────┘
         │                  │                       │                  │
┌────────────────────────────────────┐      ┌───────────────────────────────────┐
│              Client 1              │      │             Client 2              │
│           (Primary)                │      │          (Secondary)              │
└────────────────────────────────────┘      └───────────────────────────────────┘
   --------------------------- Client Services ------------------------------
                 │                                            │
                 ▼                                            ▼
┌──────────────────────────────────┐        ┌──────────────────────────────────┐
│          WebSocket 1             │        │          WebSocket 2             │
│     (Client 1 Connection)        │        │     (Client 2 Connection)        │
└──────────────────────────────────┘        └──────────────────────────────────┘
                 │                                            │
                 ▼                                            ▼
   ---------------------------- Server Service ------------------------------
┌──────────────────────────────────────────────────────────────────────────────┐
│                                 SERVER                                       │
│                          (Routes between clients)                            │
│                        Active client failover logic                          │
└──────────────────────────────────────────────────────────────────────────────┘
                           │                      │
                  ┌──────────────────┐   ┌──────────────────┐
                  │    Tunnel 1      │   │    Tunnel 2      │
                  │     Connect      │   │     Listen       │
                  │     Socket       │   │     Socket       │
                  └──────────────────┘   └──────────────────┘
   ---------------------------- Server Service ------------------------------
                           │                      ▲
                           ▼                      │
                     send/receive            send/receive
                  ┌──────────────────┐   ┌──────────────────┐
                  │   External XS1   │   │   External XS2   │
                  │   Other Site     │   │   Other Site     │
                  └──────────────────┘   └──────────────────┘


Legend:
────► Direction of Connection              
                                           
                                           
```



TCP over WebSocket is a Python 3.9+ service that provides high-availability TCP tunneling through WebSocket connections. It enables secure, reliable forwarding of TCP traffic through HTTP/HTTPS WebSocket connections with automatic failover between two clients.

## Overview

This package provides TCP-over-WebSocket tunneling with high availability failover:

- **Tunnel TCP connections** through HTTP WebSocket connections
- **Multiplex multiple TCP streams** over a single WebSocket connection
- **OPTIONALLY secured** with HTTPS and mutual TLS client certificate authentication
- **High availability** with automatic failover between two client endpoints
- **Windows service support** for production deployments

External TCP sockets connect to TCP ports on the server, which tunnels the traffic over WebSocket to TCP tunnel endpoints running on clients. TCP tunnels are bidirectional once the WebSocket connection is established.

Each TCP tunnel is defined by a `tunnelName` - the server side listens for TCP connections while the client side connects to external TCP sockets.

## Architecture

The service implements a server + two-client architecture for TCP tunneling over WebSocket with configurable tunnels:

- **Server**: Hosts TCP tunnel listen endpoints where external applications connect to access remote TCP services through WebSocket tunnels
- **Client 1**: Primary client that hosts TCP tunnel connect endpoints to external TCP services 
- **Client 2**: Secondary client that provides backup connectivity to the same external TCP services

**Tunnel Configuration**: Each tunnel is defined by a unique `tunnelName` and can be configured in either direction:
- **TCP Listen tunnels**: Server listens on a port, client connects to external service
- **TCP Connect tunnels**: Server connects to external service, client listens on a port

External applications connect to TCP ports on one side, and the service tunnels that traffic over WebSocket connections to TCP endpoints on the other side. Only one client is "active" at any time - when the active client becomes unavailable, automatic failover occurs to the standby client.

The WebSocket connection multiplexes all configured tunnels, with each tunnel identified by its unique name for proper routing.

## Key Features

### High Availability
- Automatic failover between two tunnel endpoints
- Server routes TCP tunnel traffic to the active client
- Graceful failover with configurable socket closure timing
- No single point of failure for TCP socket connectivity

### Security
- Optional SSL/TLS encryption for WebSocket connections
- Mutual TLS (client certificate) authentication
- Certificate-based peer verification
- Support for custom CA certificate chains

### Reliable TCP Tunneling
- Packet sequencing ensures ordered TCP data delivery over WebSocket transport
- Connection multiplexing allows multiple TCP streams over single WebSocket
- Automatic WebSocket reconnection maintains tunnel availability
- Data buffering handles out-of-sequence packets from WebSocket layer

### Platform Support
- Cross-platform (Linux, Windows, macOS)
- Windows service integration with proper service lifecycle
- Docker containerization with comprehensive test suite
- Configurable logging with rotation and syslog support

## Installing

Install with the following command

```
pip install tcp-over-websocket
```

NOTE: On windows, it may help to install some dependencies first, otherwise
pip may try to build them.

```
pip install vcversioner
```

## Running

You need to configure the settings before running tcp-over-websocket, but if
you want to just see if it starts run the command

```
run_tcp_over_websocket_service
```

It will start as a client by default and try to reconnect to nothing.

## Configuration

By default the tcp-over-websocket will create a home directory
~/tcp-over-websocket.home and create a `config.json` file in that directory.

To change the location of this directory, pass the config directory name in
as the first argument of the python script

Here is a windows example:

```
python c:\python\Lib\site-packages\tcp_over_websocket
\run_tcp_over_websocket_service.py c:\Users\meuser\tcp-over-websocket-server.
home
```

## High Availability Configuration

The TCP-over-WebSocket service supports a server with exactly two clients for high availability tunneling. When external sockets connect to TCP ports on the server, the traffic is routed through WebSocket connections to the "active" client, which then connects to the actual external TCP sockets. When the first data is sent to a standby client's listening socket, that client becomes active and takes over all tunnel traffic routing.

## Example Client Configuration

Clients host the TCP tunnel endpoints and connect to the server via WebSocket. Create a directory and place the following contents in a config.json file in that directory. Note the `clientId` field which must be either 1 or 2.

```json
{
    "dataExchange": {
        "enableMutualTLS": false,
        "mutualTLSTrustedCACertificateBundleFilePath": "/Users/jchesney/Downloads/tcp_svr/trusted-ca.pem",
        "mutualTLSTrustedPeerCertificateBundleFilePath": "/Users/jchesney/Downloads/tcp_svr/certs-of-peers.pem",
        "serverUrl": "http://localhost:8080",
        "tlsBundleFilePath": "/Users/jchesney/Downloads/tcp_svr/key-cert-ca-root-chain.pem"
    },
    "logging": {
        "daysToKeep": 14,
        "level": "DEBUG",
        "logToStdout": true,
        "syslog": {
            "logToSysloyHost": null
        }
    },
    "tcpTunnelConnects": [
        {
            "connectToHost": "search.brave.com",
            "connectToPort": 80,
            "tunnelName": "brave"
        },
        {
            "connectToHost": "127.0.0.1",
            "connectToPort": 22,
            "tunnelName": "test_ssh"
        }
    ],
    "tcpTunnelListens": [
        {
            "listenBindAddress": "127.0.0.1",
            "listenPort": 8091,
            "tunnelName": "duckduckgo"
        }],
    "weAreServer": false,
    "clientId": 1
}
```

## Example Second Client Configuration

For the second client, use the same configuration but with `clientId: 2` and
different port numbers to avoid conflicts:

```json
{
    "dataExchange": {
        "serverUrl": "http://localhost:8080"
    },
    "tcpTunnelListens": [
        {
            "listenBindAddress": "127.0.0.1",
            "listenPort": 8094,
            "tunnelName": "duckduckgo"
        }],
    "weAreServer": false,
    "clientId": 2
}
```

## Example Server Configuration

The server provides TCP tunnel endpoints that external sockets connect to. Traffic is then routed over WebSocket to external TCP sockets accessible through the active client.

```json
{
    "dataExchange": {
        "enableMutualTLS": false,
        "mutualTLSTrustedCACertificateBundleFilePath": "/Users/jchesney/Downloads/tcp_svr/trusted-ca.pem",
        "mutualTLSTrustedPeerCertificateBundleFilePath": "/Users/jchesney/Downloads/tcp_svr/certs-of-peers.pem",
        "serverUrl": "http://localhost:8080",
        "tlsBundleFilePath": "/Users/jchesney/Downloads/tcp_svr/key-cert-ca-root-chain.pem"
    },
    "logging": {
        "daysToKeep": 14,
        "level": "DEBUG",
        "logToStdout": true,
        "syslog": {
            "logToSysloyHost": null
        }
    },
    "tcpTunnelConnects": [
        {
            "connectToHost": "duckduckgo.com",
            "connectToPort": 80,
            "tunnelName": "duckduckgo"
        }
    ],
    "tcpTunnelListens": [
        {
            "listenBindAddress": "127.0.0.1",
            "listenPort": 8092,
            "tunnelName": "brave"
        },
        {
            "listenBindAddress": "127.0.0.1",
            "listenPort": 8022,
            "tunnelName": "test_ssh"
        }
    ],
    "weAreServer": true
}
```

## What Can Connect to TCP Tunnels

The TCP-over-WebSocket service works with any TCP socket connections. Examples of what might connect to these external TCP sockets include:

- **Web servers** (HTTP/HTTPS on ports 80/443)
- **Database servers** (MySQL on 3306, PostgreSQL on 5432, etc.)  
- **SSH servers** (typically port 22)
- **Application servers** (custom TCP protocols)
- **Message brokers** (MQTT, RabbitMQ, etc.)
- **Remote desktop services** (RDP, VNC)
- **Any TCP-based service** that accepts socket connections

The service treats all connections as raw TCP data streams - it doesn't inspect or modify the content, making it protocol-agnostic.

### Configuration Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `clientId` | Client identifier (1 or 2) for HA setup | 1 |
| `weAreServer` | Whether this instance hosts TCP tunnel endpoints | false |
| `serverUrl` | WebSocket server URL for tunnel transport | http://localhost:8080 |
| `standbySocketCloseDurationSecs` | Socket close duration during failover | 30 |
| `enableMutualTLS` | Enable mutual TLS authentication | false |

## Running the Service

### Command Line

```bash
# Server
run_tcp_over_websocket_service /path/to/server/config

# Client 1  
run_tcp_over_websocket_service /path/to/client1/config

# Client 2
run_tcp_over_websocket_service /path/to/client2/config
```

## Windows Services

To install tcp-over-websocket, open a command prompt as administrator, and run
the following command.

```
winsvc_tcp_over_websocket_service --username .\user-svc --password "myPa$$" --startup auto install
  
```

Use `--username` and `--password` to run the service as a non-privileged user.

---

After registering the above, you must go and re-enter the username and password.

1. Run `servcies.msc`
2. Find the `TCP over Websocket` service
3. Open the service properties
4. Click on the `Lok On` tab
5. Click `Local System account` and click `Apply`
6. Select `This account`
7. Enter your service username and password again.
8. Click `Ok`
9. You will then get an alert saying your service user has been granted
   permissions to `log on as a service`

---

Consider making the service restart on failure.

1. Again, Open the properties of the service in `services.msc`
2. Click on the `Recovery` tab
3. Change the `First failure` dropdown box to `Restart the Service`
4. Click `Ok`

## Server Side TLS

Never run this service with out client TLS, and especially not without
server TLS.

NOTE: The following all assumes you have x509 certificates in ascii format.

Prepare the standard server side TLS bundle with a command similar to:

```

# Create the file containing the server or client certificates that either 
# will send.
cat Root.crt CA.crt MyServerCert.{crt,key} > key-cert-ca-root-chain.pem

# or
cat Root.crt CA.crt MyClientCert.{crt,key} > key-cert-ca-root-chain.pem


```

--

Configure the server to service on SSL:

1. Update both client and server configurations `serverUrl` to start with
   `https`
2. Ensure the `tlsBundleFilePath` setting points to your pem bundle as
   prepared in the code block above.
3. Restart both client and server services.

## Mutual TLS

Mutual TLS or Client Certificate Authentication is when the client also
sends certificates to the server, and the server verifies them.

In our case, our client also verifies that the server has provided a
specific trusted certificate.

---

For Mutual TLS / Client Certificate Authentication, ensure you have a
certificate that has Client and Server capabilities.

```
# Run
openssl x509 -in mycert.crt -text | grep Web

# Expect to see
#                 TLS Web Server Authentication, TLS Web Client Authentication
```

---

Prepare the certificates for mutual TLS, the same commands work for both
sides, however, you put the servers certificates in the clients mutualTLS
config and the clients certificates in the servers mutualTLS config.

```
# Create the file that contains the certificate chain of the trusted 
certificates.

cat Root.crt CA.crt > mtls/trusted-ca-chain.pem

# Create the file containing the peer certificates to trust
cat MyServerCert.{crt,key} > certs-of-peers.pem

# or 
cat MyClientCert.{crt,key} > certs-of-peers.pem

```

---

To configure Mutual TLS, we will:

* Tell the client to send it's own certificat and chain
* Tell both the client and server what certificates to accept from the other

On the Server

1. Set the `enableMutualTLS` to `true`
2. Set the `mutualTLSTrustedCACertificateBundleFilePath` value to the path
   of a file containing the Clients root and certificate authority
   certificates.
3. Set the `mutualTLSTrustedPeerCertificateBundleFilePath` to the path of a
   file containing the Clients public certificate.

On the Client

1. Set the `tlsBundleFilePath` as per the last section.
2. Set the `enableMutualTLS` to `true`
3. Set the `mutualTLSTrustedCACertificateBundleFilePath` value to the path
   of a file containing the Servers root and certificate authority
   certificates.
4. Set the `mutualTLSTrustedPeerCertificateBundleFilePath` to the path of a
   file containing the Servers public certificate.

## Testing

The TCP over WebSocket service includes a comprehensive test suite that validates functionality across multiple scenarios. There are three different methods for running the unit tests:

### 1. Docker Containers (Recommended for CI/Integration Testing)

The Docker approach provides the most isolated and reproducible testing environment.

**Prerequisites:**
```bash
./docker/build.sh
docker-compose -f docker/docker-compose.yml up -d
```

**Run all tests:**
```bash
docker-compose -f docker/docker-compose.yml --profile test up --build
```

**Run tests with verbose output:**
```bash
docker-compose -f docker/docker-compose.yml --profile test run --rm tests /app/run_tests.sh --verbose
```

**Architecture:**
The Docker setup includes:
- **Server** (`tcp-over-websocket-server`) - Routes traffic between clients
- **Client 1** (`tcp-over-websocket-client1`) - First client with `clientId: 1`
- **Client 2** (`tcp-over-websocket-client2`) - Second client with `clientId: 2`
- **Tests** (`tcp-over-websocket-tests`) - Test runner with comprehensive test suites

**Port Configuration:**
- Server: 38080 (WebSocket), 38001-38002 (server-to-client tunnels)
- Client 1: 38011-38012 (client-to-server tunnels)
- Client 2: 38031-38032 (mapped to 38021-38022 internally)

### 2. run_test_suite_locally.py (Recommended for Full Local Testing)

This method orchestrates all services and tests locally using subprocess management.

**Prerequisites:**
```bash
pip install -r requirements.txt
pip install -r tests/requirements.txt
```

**Run the complete test suite:**
```bash
python tests/run_test_suite_locally.py
```

**Features:**
- Automatically starts and stops all three services (server, client1, client2)
- Runs all test suites sequentially with proper cleanup
- Captures and logs output from all services and tests
- Provides comprehensive test reporting with pass/fail counts
- Handles port conflicts and process cleanup
- Saves detailed logs to `test-logs/` directory

### 3. Running Services and Tests Individually (Best for Development)

This method gives you full control over each component, ideal for development and debugging specific issues.

**Step 1: Start Services Manually**
```bash
# Terminal 1 - Start Server
python tests/run_test_server_service.py

# Terminal 2 - Start Client 1
python tests/run_test_client1_service.py

# Terminal 3 - Start Client 2
python tests/run_test_client2_service.py
```

**Step 2: Run Individual Tests**
```bash
# Run specific test suite
pytest tests/test_suite_1_basic_echo.py -v

# Run specific test
pytest tests/test_suite_1_basic_echo.py::TestBasicEcho::test_1_1_server_to_client_tun1_echo -v

# Run with specific markers
pytest tests/ -m "not slow" -v        # Skip slow tests
pytest tests/ -m "failover" -v        # Run only failover tests
```

**Step 3: Development Workflow**
```bash
# Run all tests with detailed output
pytest tests/ -v --asyncio-mode=auto --tb=short

# Run failed tests only
pytest tests/ --lf -v

# Run with coverage
pytest tests/ --cov=tcp_over_websocket --cov-report=html
```

### Test Suites

The test suite covers comprehensive functionality validation:

1. **Basic Echo Tests (Suite 1)** - Simple connectivity validation with both clients
2. **Data Quality Tests (Suite 2)** - 100MB transfers with SHA-256 checksum validation  
3. **Ping Pong Tests (Suite 3)** - 1000 iterations with 10ms delays and 500-byte packets
4. **Performance Tests (Suite 4)** - 5GB bidirectional transfers with throughput measurement
5. **Concurrent Connection Tests (Suite 5)** - Multiple simultaneous connections and sequential cycles
6. **Failover Impact Tests (Suite 6)** - Behavior validation during client transitions

### Test Configuration

Tests use dedicated configurations in `test_config/`:
- `websocket_server/config.json` - Server test configuration
- `websocket_client_1/config.json` - Client 1 test configuration  
- `websocket_client_2/config.json` - Client 2 test configuration

### Interpreting Results

Each test provides:
- **Pass/Fail status** with detailed error messages
- **Performance metrics** (throughput, latency, connection rates)
- **Data integrity validation** via SHA-256 checksums
- **Connection state logging** for debugging failover scenarios
- **Comprehensive logs** saved to `test-logs/` directory

## Package Architecture

### Core Classes

#### **FileConfig** (`config/file_config.py`)
Main configuration class providing typed access to all settings:
- Manages `clientId` (1 or 2) for high availability setup
- Determines if instance is server (`weAreServer` boolean)
- Loads TCP tunnel listen and connect configurations
- Integrates data exchange and logging configurations

#### **ActiveRemoteController** (`controllers/active_remote_controller.py`)
High availability manager that handles client switching:
- Tracks which client (1 or 2) is currently active
- Records tunnel connections to determine active client
- Sends kill signals to inactive client connections
- Manages client online/offline state tracking
- Implements automatic failover when active client disconnects

#### **TcpTunnelABC** (`tcp_tunnel/tcp_tunnel_abc.py`)
Abstract base class that defines the core tunneling protocol:
- Manages WebSocket ↔ TCP data flow with packet sequencing
- Handles connection lifecycle (made/lost/closed) events
- Implements packet ordering and buffering logic
- Provides control message handling (connection status)

### Entry Points

#### **run_tcp_over_websocket_service.py**
Main service entry point:
- Initializes Twisted reactor and WebSocket factories
- Sets up server or client mode based on configuration
- Creates and manages all TCP tunnels
- Handles WebSocket connection establishment and monitoring

#### **winsvc_tcp_over_websocket_service.py**
Windows service wrapper:
- Integrates with Windows Service Control Manager
- Provides service installation, start, stop, and removal
- Handles Windows service lifecycle events

## Python 3.9 Compatibility

This project is designed for Python 3.9+ and uses modern Python features:

- Type hints with `typing` module annotations
- f-string formatting throughout
- `pathlib.Path` for cross-platform file operations
- Modern async/await patterns with Twisted's `inlineCallbacks`

### Dependencies

All dependencies are verified compatible with Python 3.9:

- `twisted[tls]==22.10.0` - Async networking and WebSocket support
- `vortexpy==3.4.3` - Message routing and WebSocket abstraction  
- `reactivex==4.0.4` - Reactive observables for event handling
- `json-cfg-rw==0.5.0` - JSON configuration file management
- `txhttputil==1.2.8` - HTTP utilities for Twisted

## Troubleshooting

### Common Issues

**Connection Refused**
- Verify server is running and accessible
- Check firewall settings and port availability
- Validate `serverUrl` in client configuration

**Failover Not Working**  
- Ensure both clients have different `clientId` values (1 and 2)
- Check `standbySocketCloseDurationSecs` configuration
- Verify both clients can connect to server

**Certificate Errors**
- Validate certificate file paths exist and are readable
- Check certificate format (PEM) and content
- Ensure certificate chains are complete

**High Memory Usage**
- Monitor connection counts and data buffer sizes
- Check for connection leaks in TCP socket code
- Consider adjusting packet sizes for large transfers

### Test Troubleshooting

If tests fail:

1. **Check service status** (for run_test_suite_locally.py):
   ```bash
   # Check if ports are in use
   netstat -tulpn | grep -E "(38080|38001|38002|38011|38012|38021|38022)"
   
   # Kill existing processes
   pkill -f run_test
   ```

2. **Check Docker container status**:
   ```bash
   docker-compose -f docker/docker-compose.yml ps
   docker-compose -f docker/docker-compose.yml logs
   ```

3. **View detailed logs**:
   ```bash
   # Local test logs
   ls -la test-logs/
   
   # Docker test logs  
   docker-compose -f docker/docker-compose.yml logs tests
   ```

4. **Run specific failing test**:
   ```bash
   pytest tests/test_suite_2_data_quality.py::TestDataQuality::test_2_1_100mb_server_to_client_tun1 -v -s
   ```

### Performance Tuning

**For High Throughput:**
- Increase OS socket buffers
- Use dedicated network interfaces
- Monitor CPU usage during large transfers

**For Many Connections:**
- Adjust OS file descriptor limits
- Monitor memory usage for connection tracking
- Consider connection pooling in external TCP socket code

## License

MIT License - see LICENSE file for full text.