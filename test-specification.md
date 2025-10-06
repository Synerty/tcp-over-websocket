[# TCP-over-WebSocket Tunnel Testing Specification (Simplified)

## Overview

This specification defines focused tests for a TCP-over-WebSocket tunnel system with active/standby client failover. Each test validates one specific aspect of the system.

**Test Philosophy**: One test, one validation. Build complexity incrementally.

## System Architecture

### Components
- **Server**: Central tunnel coordinator, routes to active client
- **Client 1**: Primary client with tunnel endpoints
- **Client 2**: Secondary client with tunnel endpoints (standby)
- **Test Container**: Echo servers on backend ports

### Port Configuration

All ports are read from configuration files via `port_config.PortConfig`. Use the following properties:

**Server Ports**:
- `portConfig.serverToClientTun1ListenPort` - Server listen for server-to-client-tun1
- `portConfig.serverToClientTun2ListenPort` - Server listen for server-to-client-tun2

**Client 1 Ports**:
- `portConfig.client1ToServerTun1ListenPort` - Client1 listen for client-to-server-tun1
- `portConfig.client1ToServerTun2ListenPort` - Client1 listen for client-to-server-tun2

**Client 2 Ports**:
- `portConfig.client2ToServerTun1ListenPort` - Client2 listen for client-to-server-tun1
- `portConfig.client2ToServerTun2ListenPort` - Client2 listen for client-to-server-tun2

**Backend Echo Server Ports**:
- `portConfig.serverToClient1Tun1ConnectPort` - Client1 backend (server-to-client-tun1)
- `portConfig.serverToClient1Tun2ConnectPort` - Client1 backend (server-to-client-tun2)
- `portConfig.serverToClient2Tun1ConnectPort` - Client2 backend (server-to-client-tun1)
- `portConfig.serverToClient2Tun2ConnectPort` - Client2 backend (server-to-client-tun2)
- `portConfig.clientToServerTun1ConnectPort` - Shared backend (client-to-server-tun1)
- `portConfig.clientToServerTun2ConnectPort` - Shared backend (client-to-server-tun2)

**Failover Wait Time**: `portConfig.reconnectTimeoutSecs + 2` seconds

## Test Suites

### 1. Basic Echo Tests

Tests basic connectivity and echo functionality. Initial tests use Client 1, then failover occurs, followed by tests on Client 2.

Each test creates its own TestConnection instance(s).

#### Test 1.1: Server-to-Client Tunnel 1 Echo
- Get port from `portConfig.serverToClientTun1ListenPort`
- Connect to server:port
- Send "HELLO"
- Receive response
- Check response contains "HELLO"
- Close connection

#### Test 1.2: Client-to-Server Tunnel 1 Echo
- Get port from `portConfig.client1ToServerTun1ListenPort`
- Connect to client1:port
- Send "WORLD"
- Receive response
- Check response contains "WORLD"
- Close connection

#### Test 1.3: Combined Tunnels (Tun1) Sequential
- Get server port from `portConfig.serverToClientTun1ListenPort`
- Connect to server:port
- Send "SERVER"
- Check response contains "SERVER"
- Close connection
- Get client port from `portConfig.client1ToServerTun1ListenPort`
- Connect to client1:port
- Send "CLIENT"
- Check response contains "CLIENT"
- Close connection

#### Test 1.4: Both Tunnels Simultaneously
- Get ports from `portConfig.serverToClientTun1ListenPort` and `portConfig.serverToClientTun2ListenPort`
- Open connection to server:tun1_port
- Open connection to server:tun2_port
- Send "TUN1" to server:tun1_port
- Send "TUN2" to server:tun2_port
- Receive both responses
- Check server:tun1_port response contains "TUN1"
- Check server:tun2_port response contains "TUN2"
- Close both connections

#### Test 1.5: Failover Event
- Get port from `portConfig.client2ToServerTun1ListenPort`
- Trigger failover by connecting to client2:port and sending first data
- Close client2 connection
- Get wait time from `portConfig.reconnectTimeoutSecs + 2`
- Wait for calculated seconds
- No validation, just wait for system to settle

#### Test 1.6-1.9: Repeat Tests 1.1-1.4 for Client 2
- Same tests as 1.1-1.4
- Use `portConfig.client2ToServerTun1ListenPort` and `portConfig.client2ToServerTun2ListenPort`
- Verify routing to client2 backends

### Failover Testing Specification



#### Test Setup
- Test 1: Reset system to client 1 as active

#### Connection Persistence Tests (Tests 2-5)

The aim of this test is to ensure that new connections that cause a failover
remain connected during the failover process.

Test that during failover:
- Establish connection to standby
- Send one message per second for 30 seconds
- Connection maintains for full 30 seconds
- All data successfully received
- Connection closes cleanly
- The order of tests are, client 2, client 1, client 2, client1 

#### Primary Server Port Closure Tests (Tests 6-9)
The purpose of this test is to ensure the server closes, waits and reopens 
the ports its listening on for the tcp tunnels.

Test that after failover:
- Monitor open ports on the server that was active
- Verify listening sockets close within 1 second
- Verify sockets reopen at configured timeout ±1 second
- The order of tests are, client 2, client 1, client 2, client1 

#### New Standby Port Closure Tests (Tests 10-13)
The purpose of this test is to ensure the new standby client closes, waits and 
reopens the ports its listening on for the tcp tunnels.

Test that after failover:
- Monitor open ports on the new standby (previously active server)
- Verify ports close within 1 second
- Verify ports reopen at configured timeout ±1 second
- The order of tests are, client 2, client 1, client 2, client1 

### 3. Data Quality Tests

Validates data integrity with 100MB transfers and SHA-256 checksums. Initial tests use Client 1, then failover occurs, followed by tests on Client 2.

Each test creates its own TestConnection instance(s).

#### Test 2.1: 100MB Server-to-Client Tunnel 1
- Generate 100MB deterministic data
- Calculate SHA-256 checksum of sent data
- Get port from `portConfig.serverToClientTun1ListenPort`
- Connect to server:port
- Send data
- Receive echo
- Calculate SHA-256 checksum of received data
- Check checksums match
- Close connection

#### Test 2.2: 100MB Server-to-Client Tunnel 2
- Same as 2.1 but use `portConfig.serverToClientTun2ListenPort`

#### Test 2.3: 100MB Client-to-Server Tunnel 1
- Same as 2.1 but use `portConfig.client1ToServerTun1ListenPort` and connect to client1

#### Test 2.4: 100MB Client-to-Server Tunnel 2
- Same as 2.1 but use `portConfig.client1ToServerTun2ListenPort` and connect to client1

#### Test 2.5: Failover Event
- Get port from `portConfig.client2ToServerTun1ListenPort`
- Trigger failover by connecting to client2:port and sending first data
- Close client2 connection
- Get wait time from `portConfig.reconnectTimeoutSecs + 2`
- Wait for calculated seconds

#### Test 2.6-2.9: Repeat Tests 2.1-2.4 for Client 2
- Same tests as 2.1-2.4
- Use `portConfig.client2ToServerTun1ListenPort` and `portConfig.client2ToServerTun2ListenPort`

### 4. Ping Pong Tests

1000 iterations, 10ms delay between responses, 500 byte packets. Initial tests use Client 1, then failover occurs, followed by tests on Client 2.

Each test creates its own TestConnection instance(s).

#### Test 3.1: Client-to-Server Tunnel 1 Bidirectional
- Get port from `portConfig.client1ToServerTun1ListenPort`
- Connect to client1:port
- For 1000 iterations:
    - Send 500 bytes
    - Wait to receive 500 bytes echo
    - Wait 10ms
- Calculate success rate
- Close connection
- Check success rate ≥ 95%

#### Test 3.2: Client-to-Server Tunnel 2 Bidirectional
- Same as 3.1 but use `portConfig.client1ToServerTun2ListenPort`

#### Test 3.3: Server-to-Client Tunnel 1 Bidirectional
- Same as 3.1 but use `portConfig.serverToClientTun1ListenPort` and connect to server

#### Test 3.4: Server-to-Client Tunnel 2 Bidirectional
- Same as 3.1 but use `portConfig.serverToClientTun2ListenPort` and connect to server

#### Test 3.5: Failover Event
- Get port from `portConfig.client2ToServerTun1ListenPort`
- Trigger failover by connecting to client2:port and sending first data
- Close client2 connection
- Get wait time from `portConfig.reconnectTimeoutSecs + 2`
- Wait for calculated seconds

#### Test 3.6-3.9: Repeat Tests 3.1-3.4 for Client 2
- Same tests as 3.1-3.4
- Use `portConfig.client2ToServerTun1ListenPort` and `portConfig.client2ToServerTun2ListenPort` for client-to-server tests
- Use `portConfig.serverToClientTun1ListenPort` and `portConfig.serverToClientTun2ListenPort` for server-to-client tests

### 5. Multiple Concurrent Connections

Tests multiple connections opening and closing simultaneously. Each test creates multiple TestConnection instances.

#### Test 4.1: 10 Concurrent Connections - Client 1
- Get port from `portConfig.client1ToServerTun1ListenPort`
- Open 10 connections to client1:port
- For each connection:
    - Send unique 1KB data
    - Receive echo
    - Validate echo matches sent data
- Close all connections
- Check ≥ 9 connections succeeded

#### Test 4.2: 10 Concurrent Connections - Server-to-Client
- Get port from `portConfig.serverToClientTun1ListenPort`
- Open 10 connections to server:port
- Same validation as 4.1
- Check ≥ 9 connections succeeded

#### Test 4.3: 20 Sequential Connection Cycles - Client 1
- Get port from `portConfig.client1ToServerTun1ListenPort`
- For 20 iterations:
    - Open connection to client1:port
    - Send 512 bytes
    - Receive echo
    - Validate
    - Close connection
- Check ≥ 18 iterations succeeded

#### Test 4.4: Failover Event
- Get port from `portConfig.client2ToServerTun1ListenPort`
- Trigger failover by connecting to client2:port and sending first data
- Close client2 connection
- Get wait time from `portConfig.reconnectTimeoutSecs + 2`
- Wait for calculated seconds

#### Test 4.5-4.7: Repeat Tests 4.1-4.3 for Client 2
- Same tests as 4.1-4.3
- Use `portConfig.client2ToServerTun1ListenPort` and `portConfig.serverToClientTun1ListenPort`

### 6. Failover Impact Tests

These tests are designed to test the behaviof of connected sockets during
failover.

Not Implemented.

### 7. Maximum Punishment Tests

Stress testing with 100 concurrent connections using random transfer sizes and limited concurrency. Transfer sizes range from 100KB to 250MB with weighted distribution toward smaller transfers. Only transfers ≤5MB get SHA-256 checksum validation for performance reasons.

Each test creates 100 concurrent connections with maximum 20 active at once.

#### Test 6.1: 100 Concurrent Transfers - Client-to-Server Tunnel 1
- Generate 100 random transfer sizes (100KB-250MB, weighted toward smaller)
- Get port from `portConfig.client1ToServerTun1ListenPort`
- Create 100 connections to client1:port
- Generate unique deterministic data for each connection
- Run transfers with max 20 concurrent (using semaphore)
- For transfers ≤5MB: validate SHA-256 checksums
- For all transfers: validate length matches
- Measure overall throughput
- Close all connections
- Check ≥95 transfers succeeded

#### Test 6.2: 100 Concurrent Transfers - Server-to-Client Tunnel 1
- Same as 6.1 but use `portConfig.serverToClientTun1ListenPort` and connect to server

#### Test 6.3: Failover Event
- Get port from `portConfig.client2ToServerTun1ListenPort`
- Trigger failover by connecting to client2:port and sending first data
- Close client2 connection
- Get wait time from `portConfig.reconnectTimeoutSecs + 2`
- Wait for calculated seconds

#### Test 6.4: 100 Concurrent Transfers - Client-to-Server Tunnel 1 (Client 2)
- Same as 6.1 but use `portConfig.client2ToServerTun1ListenPort`

#### Test 6.5: 100 Concurrent Transfers - Server-to-Client Tunnel 1 (Client 2)
- Same as 6.2 but routes to client 2 backends

#### Test 6.6: Back to Client 1 Failover
- Get port from `portConfig.client1ToServerTun1ListenPort`
- Trigger failover back to client1 by connecting to client1:port and sending first data
- Close client1 connection
- Get wait time from `portConfig.reconnectTimeoutSecs + 2`
- Wait for calculated seconds

## Validation Requirements

### Data Integrity
- All tests receiving echo responses must validate data correctness
- Large transfers (≥100MB) must use SHA-256 checksum validation
- Small transfers (<100MB) must validate exact content match
- Maximum punishment tests: Only transfers ≤5MB get SHA-256 validation for performance

### Connection Success Rates
- Single connection tests: 100% success required
- Concurrent tests (≤20 connections): ≥90% success rate acceptable
- Ping-pong tests: ≥95% success rate acceptable
- Maximum punishment tests (100 connections): ≥95% success rate acceptable

### Failover Behavior
- Failover tests only validate data integrity, not connection stability
- Expected: Some data loss or connection drops during failover
- Validation: Check first 50 bytes of received data only

## Test Implementation

### Framework
- Python 3.9+ with asyncio
- pytest with pytest-asyncio
- Class-based test suites
- Each test method is independent

### Test Class Template
```python
from port_config import get_port_config
from test_tcp_socket import TestTcpSocket, ConnectionEndState

class TestBasicEcho:
    """Test Suite: Basic Echo Tests"""

    @pytest.mark.asyncio
    async def test_1_1_server_to_client_tun1_echo(self):
        """Test 1.1: Server-to-Client Tunnel 1 Echo (Client 1)"""
        portConfig = get_port_config()
        
        # Start echo server on backend port that tunnel will connect to
        echoPort = portConfig.serverToClient1Tun1ConnectPort
        echoServer = TestTcpSocket("echo_backend", shouldEchoData=True)
        listening = await echoServer.startListen(port=echoPort, host="0.0.0.0")
        assert listening, f"Failed to start echo server on port {echoPort}"
        
        # Connect to tunnel endpoint
        tunnelPort = portConfig.serverToClientTun1ListenPort
        conn = TestTcpSocket("test_1_1")
        connected = await conn.startConnect("server", tunnelPort)
        assert connected, f"Failed to connect to server:{tunnelPort}"
        
        # Send data through tunnel, receive echo from backend
        sentData = b"HELLO"
        receivedData, success = await conn.sendAndReceiveEcho(sentData)
        
        await conn.close()
        await echoServer.close()
        
        assert success, "Failed to send and receive"
        assert b"HELLO" in receivedData, "Response does not contain HELLO"

    @pytest.mark.asyncio
    async def test_1_5_failover_event(self):
        """Test 1.5: Failover Event"""
        portConfig = get_port_config()
        waitTime = portConfig.reconnectTimeoutSecs + 2
        
        # Start echo server for client2 tunnel
        echoPort = portConfig.clientToServerTun1ConnectPort
        echoServer = TestTcpSocket("echo_failover", shouldEchoData=True)
        listening = await echoServer.startListen(port=echoPort, host="0.0.0.0")
        assert listening, f"Failed to start echo server on port {echoPort}"
        
        # Trigger failover by connecting to client2
        tunnelPort = portConfig.client2ToServerTun1ListenPort
        conn = TestTcpSocket("failover_trigger")
        connected = await conn.startConnect("client2", tunnelPort)
        assert connected, f"Failed to connect to client2:{tunnelPort}"
        
        await conn.close()
        await echoServer.close()
        
        # Wait for failover to complete
        logger.info(f"Waiting {waitTime}s for failover to complete")
        await asyncio.sleep(waitTime)
        logger.info("Failover wait complete")
```

### Connection Management
- Each test creates its own TestTcpSocket instances using `startConnect()` or `startListen()`
- Each test closes its connections before completion using `await conn.close()`
- No shared connections between tests
- Wait 1 second between tests (pytest handles this)

### Using UtilTcpSocket for Echo Servers
```python
# Create an echo server that listens on a port
echoServer = UtilTcpSocket("echo_server", shouldEchoData=True)
await echoServer.startListen(port=39001, host="0.0.0.0")

# Server will automatically echo data back to clients
# Clean up when done
await echoServer.close()
```

### Error Handling
- Expected errors during failover: BrokenPipeError, ConnectionResetError
- Log expected errors at INFO level
- Log unexpected errors at ERROR level with stack traces
- Tests expecting failover should set `conn.setExpectedEndState(ConnectionEndState.EXPECTED_FAILOVER)`

## Execution Order

1. Suite 1: Basic Echo Tests (9 tests)
2. Suite 2: Basic Failover Tests (10 tests)
3. Suite 3: Data Quality Tests (10 tests)
4. Suite 4: Ping Pong Tests (10 tests)
5. Suite 5: Multiple Concurrent Connections (8 tests)
6. Suite 6: Failover Impact Tests (5 tests)
7. Suite 7: Maximum Punishment Tests (6 tests)

**Total: 58 tests across 7 test suites**

## Metrics Collection

### Per Test
- Test duration
- Bytes sent/received
- Success/failure status
- Error messages if failed

### Per Suite
- Total suite duration
- Pass/fail count
- Success rate

### System-Wide
- Total test duration
- Overall pass/fail ratio
- Performance metrics (throughput, latency)]()