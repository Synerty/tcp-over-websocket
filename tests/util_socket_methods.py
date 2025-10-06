import asyncio
import logging
import os
import socket
import time
from typing import Callable
from typing import Dict
from typing import List
from typing import Optional

from util_port_config import get_port_config
from util_tcp_socket import UtilTcpSocket

logger = logging.getLogger("test_suite_runner")


class SocketDowntimeTracker:
    """Helper class to track socket downtime during failover operations"""

    def __init__(self):
        self.downtimeRecords: Dict[str, List[Dict]] = {}

    def startTracking(self, socketName: str, host: str, port: int):
        """Start tracking downtime for a specific socket"""
        if socketName not in self.downtimeRecords:
            self.downtimeRecords[socketName] = []

        record = {
            "host": host,
            "port": port,
            "startTime": time.time(),
            "endTime": None,
            "totalDowntime": 0.0,
            "checkCount": 0,
        }
        self.downtimeRecords[socketName].append(record)
        logger.info(
            f"Started tracking downtime for {socketName} ({host}:{port})"
        )

    async def trackUntilAvailable(
        self,
        socketName: str,
        maxWaitSecs: int = 30,
        checkIntervalSecs: float = 0.5,
    ) -> float:
        """Track socket until it becomes available, return total downtime"""
        if (
            socketName not in self.downtimeRecords
            or not self.downtimeRecords[socketName]
        ):
            logger.error(f"No tracking record found for {socketName}")
            return 0.0

        record = self.downtimeRecords[socketName][-1]  # Get latest record
        if record["endTime"] is not None:
            logger.warning(f"Socket {socketName} tracking already completed")
            return record["totalDowntime"]

        host = record["host"]
        port = record["port"]
        startTime = record["startTime"]

        logger.info(
            f"Tracking {socketName} until available (max {maxWaitSecs}s)"
        )

        while (time.time() - startTime) < maxWaitSecs:
            record["checkCount"] += 1

            if checkPortOpen(host, port, timeout=0.1):
                record["endTime"] = time.time()
                record["totalDowntime"] = (
                    record["endTime"] - record["startTime"]
                )
                logger.info(
                    f"{socketName} became available after {record['totalDowntime']:.2f}s ({record['checkCount']} checks)"
                )
                return record["totalDowntime"]

            await asyncio.sleep(checkIntervalSecs)

        # Timeout reached
        record["endTime"] = time.time()
        record["totalDowntime"] = record["endTime"] - record["startTime"]
        logger.warning(
            f"{socketName} did not become available within {maxWaitSecs}s (total downtime: {record['totalDowntime']:.2f}s)"
        )
        return record["totalDowntime"]

    def getDowntimeRecord(self, socketName: str) -> Optional[Dict]:
        """Get the latest downtime record for a socket"""
        if (
            socketName not in self.downtimeRecords
            or not self.downtimeRecords[socketName]
        ):
            return None
        return self.downtimeRecords[socketName][-1]

    def getAllDowntimes(self) -> Dict[str, float]:
        """Get total downtime for all tracked sockets"""
        downtimes = {}
        for socketName, records in self.downtimeRecords.items():
            totalDowntime = sum(
                record["totalDowntime"]
                for record in records
                if record["totalDowntime"] > 0
            )
            downtimes[socketName] = totalDowntime
        return downtimes

    def logSummary(self):
        """Log a summary of all tracked socket downtimes"""
        logger.info("Socket Downtime Summary:")
        for socketName, records in self.downtimeRecords.items():
            for i, record in enumerate(records):
                if record["totalDowntime"] > 0:
                    logger.info(
                        f"  {socketName}[{i}]: {record['totalDowntime']:.2f}s downtime ({record['checkCount']} checks)"
                    )
                else:
                    logger.info(
                        f"  {socketName}[{i}]: Still tracking or no downtime recorded"
                    )


async def measureSocketDowntime(
    host: str, port: int, socketName: str, maxWaitSecs: int = 30
) -> float:
    """Measure how long a socket is down from the current moment"""
    tracker = SocketDowntimeTracker()
    tracker.startTracking(socketName, host, port)
    return await tracker.trackUntilAvailable(socketName, maxWaitSecs)


def checkPortOpen(host: str, port: int, timeout: float = 1.0) -> bool:
    """Check if a port is open without establishing a full connection"""

    if "HOST_DOCKERNAMES" not in os.environ:
        host = "127.0.0.1"

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()

        isOpen = result == 0
        logger.info(
            f"checkPortOpen: host {host}, port {port}"
            f" is {'open' if isOpen else 'closed'}"
        )
        return isOpen

    except Exception as e:
        return False


async def waitForCondition(
    conditionFunc: Callable[[], bool],
    timeoutSecs: int,
    intervalSecs: float = 1.0,
    description: str = "condition",
) -> tuple[bool, float]:
    """
    Wait for a condition to become true within a timeout period
    Returns (success, elapsedTime)
    """
    startTime = time.time()

    while (time.time() - startTime) < timeoutSecs:
        if conditionFunc():
            elapsedTime = time.time() - startTime
            logger.info(
                f"{description} completed after {elapsedTime:.1f} seconds"
            )

            return True, elapsedTime

        await asyncio.sleep(intervalSecs)

    elapsedTime = time.time() - startTime
    logger.warning(
        f"{description} did not complete within {timeoutSecs} seconds"
    )
    return False, elapsedTime


async def waitForConnectionRetry(
    host: str, port: int, maxRetries: int, description: str = "connection"
) -> bool:
    """
    Retry connection attempts until successful or max retries reached
    Returns True if connection succeeded
    """
    retryCount = 0

    while retryCount < maxRetries:
        logger.info(
            f"Attempt {retryCount + 1}/{maxRetries}: Trying to connect to {host}:{port}"
        )

        conn = UtilTcpSocket(f"{description}_attempt")
        connected = await conn.startConnect(host, port)

        if connected:
            logger.info(
                f"Successfully connected to {host}:{port} on attempt {retryCount + 1}"
            )
            await conn.close()
            return True
        else:
            await conn.close()
            retryCount += 1
            if retryCount < maxRetries:
                await asyncio.sleep(1.0)

    logger.error(f"Failed to connect to {host} after {maxRetries} attempts")
    return False


def waitForPortsOpenCallable(host: str, ports: List[int]) -> Callable[[], bool]:
    """
    Returns a condition function that checks if all specified ports are open
    """

    def checkAllPortsOpen() -> bool:
        for port in ports:
            if not checkPortOpen(host, port):
                return False
        return True

    return checkAllPortsOpen


async def resetActiveClient():
    """Reset to ensure Client 1 is the active client by retrying connections and checking ports"""
    portConfig = get_port_config()

    logger.info("Starting reset to active client (client 1)")

    # Start echo server for client1 tunnel
    echoPort = portConfig.clientToServerTun1ConnectPort
    echoServer = UtilTcpSocket("echo_reset_client1", shouldEchoData=True)
    listening = await echoServer.startListen(port=echoPort, host="0.0.0.0")
    assert listening, f"Failed to start echo server on port {echoPort}"

    try:
        tunnelPort = portConfig.client1ToServerTun1ListenPort

        # Connect and send data to ensure client1 is active
        conn = UtilTcpSocket("reset_client1_connection")
        connected = await conn.startConnect("client1", tunnelPort)
        assert connected, f"Failed to connect to client1:{tunnelPort}"

        # Send first data to trigger failover to client1
        await conn.write(b"0")
        await conn.close()

        # Wait for server ports to close if failover was triggered
        serverPorts = [
            portConfig.serverToClientTun1ListenPort,
            portConfig.serverToClientTun2ListenPort,
        ]

        # Check if server ports close (indicating failover was triggered)
        logger.info(
            "Checking if failover was triggered (server ports closing)..."
        )
        startTime = time.time()
        failoverTriggered = False

        while (time.time() - startTime) < 5.0:
            allClosed = True
            for port in serverPorts:
                if checkPortOpen("server", port, timeout=0.1):
                    allClosed = False
                    break

            if allClosed:
                failoverTriggered = True
                logger.info("Failover was triggered - server ports closed")
                break

            await asyncio.sleep(0.2)

        if failoverTriggered:
            # Wait for server ports to reopen after configured timeout
            logger.info(
                f"Waiting for server ports to reopen after {portConfig.reconnectTimeoutSecs}s timeout..."
            )
            serverPortsReopened, _ = await waitForCondition(
                waitForPortsOpenCallable("server", serverPorts),
                portConfig.reconnectTimeoutSecs + 10,
                1.0,
                description="Server ports reopening after reset",
            )

            if not serverPortsReopened:
                logger.warning(
                    f"Server ports did not reopen within expected time"
                )
        else:
            logger.info("No failover triggered - client1 was already active")

        # Ensure server ports are available
        logger.info("Ensuring server ports are available...")
        serverPortsAvailable, _ = await waitForCondition(
            waitForPortsOpenCallable("server", serverPorts),
            30,
            1.0,
            description="Server ports final availability",
        )

        if not serverPortsAvailable:
            logger.warning("Server ports are not available after reset")

        # Monitor client2 ports until they become available (standby mode)
        logger.info(
            "Waiting for client2 ports to become available (standby mode)..."
        )
        client2Ports = [
            portConfig.client2ToServerTun1ListenPort,
            portConfig.client2ToServerTun2ListenPort,
        ]

        client2PortsOpen, _ = await waitForCondition(
            waitForPortsOpenCallable("client2", client2Ports),
            portConfig.reconnectTimeoutSecs + 5,
            1.0,
            description="Client2 standby ports availability",
        )

        if not client2PortsOpen:
            logger.warning(
                f"Client2 ports did not become available"
                f" within {portConfig.reconnectTimeoutSecs + 5} seconds"
            )

        logger.info(
            "Active client reset to client 1 complete - all sockets are up"
        )

    finally:
        await echoServer.close()


async def triggerFailoverToClient2():
    """Trigger failover to client 2 and wait for completion"""
    portConfig = get_port_config()

    # Start echo server for client2 tunnel
    echoPort = portConfig.clientToServerTun1ConnectPort
    echoServer = UtilTcpSocket("echo_failover_to_client2", shouldEchoData=True)
    listening = await echoServer.startListen(port=echoPort, host="0.0.0.0")
    assert listening, f"Failed to start echo server on port {echoPort}"

    try:
        # Wait for client2 tunnel port to be available
        tunnelPort = portConfig.client2ToServerTun1ListenPort
        logger.info(
            f"Waiting for client2 tunnel port {tunnelPort} to be available..."
        )
        portAvailable, _ = await waitForCondition(
            waitForPortsOpenCallable("client2", [tunnelPort]),
            portConfig.reconnectTimeoutSecs + 5,
            1.0,
            description=f"Client2 tunnel port {tunnelPort} availability",
        )
        assert (
            portAvailable
        ), f"Client2 tunnel port {tunnelPort} not available within timeout"

        # Ensure server ports are available before triggering failover
        serverPorts = [
            portConfig.serverToClientTun1ListenPort,
            portConfig.serverToClientTun2ListenPort,
        ]
        logger.info("Ensuring server ports are available before failover...")
        serverPortsAvailable, _ = await waitForCondition(
            waitForPortsOpenCallable("server", serverPorts),
            30,
            1.0,
            description="Server ports availability before failover",
        )
        assert (
            serverPortsAvailable
        ), f"Server ports {serverPorts} not available before failover"

        # Trigger failover by connecting to client2 and sending first data
        conn = UtilTcpSocket("failover_trigger_to_client2")
        connected = await conn.startConnect("client2", tunnelPort)
        assert connected, f"Failed to connect to client2:{tunnelPort}"

        # Send first data to trigger failover
        await conn.write(b"0")
        await conn.close()

        # Wait for server ports to close (indicating failover triggered)
        logger.info(
            "Waiting for server ports to close after failover trigger..."
        )
        startTime = time.time()
        serverPortsClosed = False

        while (time.time() - startTime) < 10.0:
            allClosed = True
            for port in serverPorts:
                if checkPortOpen("server", port, timeout=0.1):
                    allClosed = False
                    break

            if allClosed:
                serverPortsClosed = True
                logger.info(
                    f"Server ports closed after {time.time() - startTime:.2f}s"
                )
                break

            await asyncio.sleep(0.2)

        if not serverPortsClosed:
            logger.warning(
                "Server ports did not close within 10 seconds after failover trigger"
            )

        # Wait for the configured downtime period plus server ports to reopen
        logger.info(
            f"Waiting for server ports to reopen after {portConfig.reconnectTimeoutSecs}s timeout..."
        )
        serverPortsReopened, _ = await waitForCondition(
            waitForPortsOpenCallable("server", serverPorts),
            portConfig.reconnectTimeoutSecs + 10,
            1.0,
            description="Server ports reopening after failover",
        )

        if not serverPortsReopened:
            logger.warning(f"Server ports did not reopen within expected time")

        # Wait for client1 ports to become available (indicating standby ready)
        logger.info(
            "Waiting for client1 ports to become available (standby mode)..."
        )
        client1Ports = [
            portConfig.client1ToServerTun1ListenPort,
            portConfig.client1ToServerTun2ListenPort,
        ]

        client1PortsAvailable, _ = await waitForCondition(
            waitForPortsOpenCallable("client1", client1Ports),
            portConfig.reconnectTimeoutSecs + 5,
            1.0,
            description="Client1 standby ports availability",
        )

        if not client1PortsAvailable:
            logger.warning(
                f"Client1 standby ports did not become available within timeout"
            )

        logger.info("Failover to client 2 complete - all sockets are up")

    finally:
        await echoServer.close()


async def triggerFailoverBackToClient1():
    """Trigger failover back to client 1 and wait for completion"""
    portConfig = get_port_config()

    # Start echo server for client1 tunnel
    echoPort = portConfig.clientToServerTun1ConnectPort
    echoServer = UtilTcpSocket(
        "echo_failover_back_to_client1", shouldEchoData=True
    )
    listening = await echoServer.startListen(port=echoPort, host="0.0.0.0")
    assert listening, f"Failed to start echo server on port {echoPort}"

    try:
        # Ensure server ports are available before triggering failover
        serverPorts = [
            portConfig.serverToClientTun1ListenPort,
            portConfig.serverToClientTun2ListenPort,
        ]
        logger.info(
            "Ensuring server ports are available before failover back..."
        )
        serverPortsAvailable, _ = await waitForCondition(
            waitForPortsOpenCallable("server", serverPorts),
            30,
            1.0,
            description="Server ports availability before failover back",
        )
        assert (
            serverPortsAvailable
        ), f"Server ports {serverPorts} not available before failover back"

        # Trigger failover back to client1 by connecting and sending first data
        tunnelPort = portConfig.client1ToServerTun1ListenPort
        conn = UtilTcpSocket("failover_trigger_back_to_client1")
        connected = await conn.startConnect("client1", tunnelPort)
        assert connected, f"Failed to connect to client1:{tunnelPort}"

        # Send first data to trigger failover
        await conn.write(b"0")
        await conn.close()

        # Wait for server ports to close (indicating failover triggered)
        logger.info(
            "Waiting for server ports to close after failover back trigger..."
        )
        startTime = time.time()
        serverPortsClosed = False

        while (time.time() - startTime) < 10.0:
            allClosed = True
            for port in serverPorts:
                if checkPortOpen("server", port, timeout=0.1):
                    allClosed = False
                    break

            if allClosed:
                serverPortsClosed = True
                logger.info(
                    f"Server ports closed after {time.time() - startTime:.2f}s"
                )
                break

            await asyncio.sleep(0.2)

        if not serverPortsClosed:
            logger.warning(
                "Server ports did not close within 10 seconds after failover back trigger"
            )

        # Wait for the configured downtime period plus server ports to reopen
        logger.info(
            f"Waiting for server ports to reopen after {portConfig.reconnectTimeoutSecs}s timeout..."
        )
        serverPortsReopened, _ = await waitForCondition(
            waitForPortsOpenCallable("server", serverPorts),
            portConfig.reconnectTimeoutSecs + 10,
            1.0,
            description="Server ports reopening after failover back",
        )

        if not serverPortsReopened:
            logger.warning(f"Server ports did not reopen within expected time")

        # Wait for client2 ports to become available (indicating standby ready)
        logger.info(
            "Waiting for client2 ports to become available (standby mode)..."
        )
        client2Ports = [
            portConfig.client2ToServerTun1ListenPort,
            portConfig.client2ToServerTun2ListenPort,
        ]

        client2PortsAvailable, _ = await waitForCondition(
            waitForPortsOpenCallable("client2", client2Ports),
            portConfig.reconnectTimeoutSecs + 5,
            1.0,
            description="Client2 standby ports availability",
        )

        if not client2PortsAvailable:
            logger.warning(
                f"Client2 standby ports did not become available within timeout"
            )

        logger.info("Failover back to client 1 complete - all sockets are up")

    finally:
        await echoServer.close()
