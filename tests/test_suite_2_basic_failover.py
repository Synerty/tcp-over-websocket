import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
import logging
import time

import pytest

from util_socket_methods import (
    resetActiveClient,
    checkPortOpen,
)
from util_port_config import get_port_config
from util_tcp_socket import ConnectionEndState, UtilTcpSocket

logger = logging.getLogger(__name__)


class TestBasicFailover:
    """Test Suite 2: Basic Failover Tests"""

    @pytest.mark.asyncio
    async def test_0_0_reset_active_client(self):
        """Test 0.0: Reset Active Client"""
        await resetActiveClient()

    @pytest.mark.asyncio
    async def test_2_1_connection_persistence_to_client2(self):
        """Test 2.1: Connection Persistence During Failover to Client 2"""
        portConfig = get_port_config()

        # Start echo server for client2 tunnel
        echoPort = portConfig.clientToServerTun1ConnectPort
        echoServer = UtilTcpSocket(
            "echo_persistence_client2", shouldEchoData=True
        )
        listening = await echoServer.startListen(port=echoPort, host="0.0.0.0")
        assert listening, f"Failed to start echo server on port {echoPort}"

        try:
            # Wait for client2 tunnel port to be available
            tunnelPort = portConfig.client2ToServerTun1ListenPort
            from util_socket_methods import (
                waitForCondition,
                waitForPortsOpenCallable,
            )

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

            # Connect to client2 (standby) to trigger failover
            conn = UtilTcpSocket("persistence_client2")
            conn.setExpectedEndState(ConnectionEndState.EXPECTED_TEST_END)
            connected = await conn.startConnect("client2", tunnelPort)
            assert connected, f"Failed to connect to client2:{tunnelPort}"

            try:
                # Send one message per second for 30 seconds during failover
                successCount = 0
                for i in range(30):
                    message = f"MSG_{i + 1:02d}"
                    sentBytes = message.encode()

                    receivedData, success = await conn.sendDataExpectEcho(
                        sentBytes, timeout=5.0
                    )
                    if success and receivedData == sentBytes:
                        successCount += 1
                        logger.debug(f"Test 2.1: Message {i + 1} successful")
                    else:
                        logger.warning(
                            f"Test 2.1: Message {i + 1} data mismatch"
                        )

                    await asyncio.sleep(1.0)

                logger.info(
                    f"Test 2.1: {successCount}/30 messages successful during failover"
                )
                assert (
                    successCount == 30
                ), f"Only {successCount}/30 messages succeeded during failover"
                logger.info(
                    "Test 2.1: Successfully maintained connection during failover to client 2"
                )
            finally:
                await conn.close()
        finally:
            await echoServer.close()

    @pytest.mark.asyncio
    async def test_2_2_connection_persistence_to_client1(self):
        """Test 2.2: Connection Persistence During Failover to Client 1"""
        portConfig = get_port_config()

        # Start echo server for client1 tunnel
        echoPort = portConfig.clientToServerTun1ConnectPort
        echoServer = UtilTcpSocket(
            "echo_persistence_client1", shouldEchoData=True
        )
        listening = await echoServer.startListen(port=echoPort, host="0.0.0.0")
        assert listening, f"Failed to start echo server on port {echoPort}"

        try:
            # Connect to client1 (now standby) to trigger failover back
            tunnelPort = portConfig.client1ToServerTun1ListenPort
            conn = UtilTcpSocket("persistence_client1")
            conn.setExpectedEndState(ConnectionEndState.EXPECTED_TEST_END)
            connected = await conn.startConnect("client1", tunnelPort)
            assert connected, f"Failed to connect to client1:{tunnelPort}"

            try:
                # Send one message per second for 30 seconds during failover
                successCount = 0
                for i in range(30):
                    message = f"MSG_{i + 1:02d}"
                    sentBytes = message.encode()

                    receivedData, success = await conn.sendDataExpectEcho(
                        sentBytes, timeout=5.0
                    )
                    if success and receivedData == sentBytes:
                        successCount += 1
                        logger.debug(f"Test 2.2: Message {i + 1} successful")
                    else:
                        logger.warning(
                            f"Test 2.2: Message {i + 1} data mismatch"
                        )

                    await asyncio.sleep(1.0)

                logger.info(
                    f"Test 2.2: {successCount}/30 messages successful during failover"
                )
                assert (
                    successCount == 30
                ), f"Only {successCount}/30 messages succeeded during failover"
                logger.info(
                    "Test 2.2: Successfully maintained connection during failover to client 1"
                )
            finally:
                await conn.close()
        finally:
            await echoServer.close()

    @pytest.mark.asyncio
    async def test_2_3_connection_persistence_to_client2_second(self):
        """Test 2.3: Connection Persistence During Failover to Client 2 (Second)"""
        portConfig = get_port_config()

        # Start echo server for client2 tunnel
        echoPort = portConfig.clientToServerTun1ConnectPort
        echoServer = UtilTcpSocket(
            "echo_persistence_client2_2nd", shouldEchoData=True
        )
        listening = await echoServer.startListen(port=echoPort, host="0.0.0.0")
        assert listening, f"Failed to start echo server on port {echoPort}"

        try:
            # Connect to client2 (standby) to trigger failover
            tunnelPort = portConfig.client2ToServerTun1ListenPort
            conn = UtilTcpSocket("persistence_client2_2nd")
            conn.setExpectedEndState(ConnectionEndState.EXPECTED_TEST_END)
            connected = await conn.startConnect("client2", tunnelPort)
            assert connected, f"Failed to connect to client2:{tunnelPort}"

            try:
                # Send one message per second for 30 seconds during failover
                successCount = 0
                for i in range(30):
                    message = f"MSG_{i + 1:02d}"
                    sentBytes = message.encode()

                    receivedData, success = await conn.sendDataExpectEcho(
                        sentBytes, timeout=5.0
                    )
                    if success and receivedData == sentBytes:
                        successCount += 1
                        logger.debug(f"Test 2.3: Message {i + 1} successful")
                    else:
                        logger.warning(
                            f"Test 2.3: Message {i + 1} data mismatch"
                        )

                    await asyncio.sleep(1.0)

                logger.info(
                    f"Test 2.3: {successCount}/30 messages successful during failover"
                )
                assert (
                    successCount == 30
                ), f"Only {successCount}/30 messages succeeded during failover"
                logger.info(
                    "Test 2.3: Successfully maintained connection during failover to client 2 (second)"
                )
            finally:
                await conn.close()
        finally:
            await echoServer.close()

    @pytest.mark.asyncio
    async def test_2_4_connection_persistence_to_client1_second(self):
        """Test 2.4: Connection Persistence During Failover to Client 1 (Second)"""
        portConfig = get_port_config()

        # Start echo server for client1 tunnel
        echoPort = portConfig.clientToServerTun1ConnectPort
        echoServer = UtilTcpSocket(
            "echo_persistence_client1_2nd", shouldEchoData=True
        )
        listening = await echoServer.startListen(port=echoPort, host="0.0.0.0")
        assert listening, f"Failed to start echo server on port {echoPort}"

        try:
            # Connect to client1 (now standby) to trigger failover back
            tunnelPort = portConfig.client1ToServerTun1ListenPort
            conn = UtilTcpSocket("persistence_client1_2nd")
            conn.setExpectedEndState(ConnectionEndState.EXPECTED_TEST_END)
            connected = await conn.startConnect("client1", tunnelPort)
            assert connected, f"Failed to connect to client1:{tunnelPort}"

            try:
                # Send one message per second for 30 seconds during failover
                successCount = 0
                for i in range(30):
                    message = f"MSG_{i + 1:02d}"
                    sentBytes = message.encode()

                    receivedData, success = await conn.sendDataExpectEcho(
                        sentBytes, timeout=5.0
                    )
                    if success and receivedData == sentBytes:
                        successCount += 1
                        logger.debug(f"Test 2.4: Message {i + 1} successful")
                    else:
                        logger.warning(
                            f"Test 2.4: Message {i + 1} data mismatch"
                        )

                    await asyncio.sleep(1.0)

                logger.info(
                    f"Test 2.4: {successCount}/30 messages successful during failover"
                )
                assert (
                    successCount == 30
                ), f"Only {successCount}/30 messages succeeded during failover"
                logger.info(
                    "Test 2.4: Successfully maintained connection during failover to client 1 (second)"
                )
            finally:
                await conn.close()
        finally:
            await echoServer.close()

    @pytest.mark.asyncio
    async def test_2_5_server_port_closure_timing_client2_failover(self):
        """Test 2.5: Primary Server Port Closure Timing During Failover to Client 2"""
        portConfig = get_port_config()

        # Start echo server for client2 tunnel
        echoPort = portConfig.clientToServerTun1ConnectPort
        echoServer = UtilTcpSocket("echo_timing_client2", shouldEchoData=True)
        listening = await echoServer.startListen(port=echoPort, host="0.0.0.0")
        assert listening, f"Failed to start echo server on port {echoPort}"

        try:
            # Start monitoring server ports before triggering failover
            serverPorts = [
                portConfig.serverToClientTun1ListenPort,
                portConfig.serverToClientTun2ListenPort,
            ]

            # Wait for server ports to be available before proceeding
            from util_socket_methods import (
                waitForCondition,
                waitForPortsOpenCallable,
            )

            logger.info("Waiting for server ports to be available...")
            portsAvailable, _ = await waitForCondition(
                waitForPortsOpenCallable("server", serverPorts),
                30,  # 30 second timeout
                1.0,  # Check every second
                description="Server ports availability",
            )
            assert (
                portsAvailable
            ), f"Server ports {serverPorts} not available within 30 seconds"

            # Trigger failover to client2
            tunnelPort = portConfig.client2ToServerTun1ListenPort
            conn = UtilTcpSocket("timing_trigger_client2")
            connected = await conn.startConnect("client2", tunnelPort)
            assert connected, f"Failed to connect to client2:{tunnelPort}"

            # Send first data to trigger failover and close immediately
            await conn.write(b"TRIGGER")
            await conn.close()

            # Monitor server ports - they should close within 1 second
            startTime = time.time()
            allClosed = False

            while (time.time() - startTime) < 5.0:  # Give 5 seconds max
                closedPorts = []
                for port in serverPorts:
                    if not checkPortOpen("server", port, timeout=0.1):
                        closedPorts.append(port)

                if len(closedPorts) == len(serverPorts):
                    closeTime = time.time() - startTime
                    allClosed = True
                    logger.info(
                        f"Test 2.5: All server ports closed after {closeTime:.2f}s"
                    )
                    assert (
                        closeTime <= 1.0
                    ), f"Server ports took {closeTime:.2f}s to close (expected ≤1s)"
                    break

                await asyncio.sleep(0.1)

            assert allClosed, "Server ports did not close within expected time"

            # Monitor server ports - they should reopen at configured timeout
            expectedTimeout = portConfig.reconnectTimeoutSecs
            startReopenTime = time.time()
            allReopened = False

            while (time.time() - startReopenTime) < (expectedTimeout + 5):
                openPorts = []
                for port in serverPorts:
                    if checkPortOpen("server", port, timeout=0.1):
                        openPorts.append(port)

                if len(openPorts) == len(serverPorts):
                    reopenTime = time.time() - startReopenTime
                    allReopened = True
                    logger.info(
                        f"Test 2.5: All server ports reopened after {reopenTime:.2f}s (expected around {expectedTimeout}s)"
                    )
                    break

                await asyncio.sleep(0.5)

            assert (
                allReopened
            ), f"Server ports did not reopen within expected time range"
            logger.info(
                "Test 2.5: Successfully validated server port closure and reopen timing during failover to client 2"
            )

        finally:
            await echoServer.close()

    @pytest.mark.asyncio
    async def test_2_6_server_port_closure_timing_client1_failover(self):
        """Test 2.6: Primary Server Port Closure Timing During Failover to Client 1"""
        portConfig = get_port_config()

        # Start echo server for client1 tunnel
        echoPort = portConfig.clientToServerTun1ConnectPort
        echoServer = UtilTcpSocket("echo_timing_client1", shouldEchoData=True)
        listening = await echoServer.startListen(port=echoPort, host="0.0.0.0")
        assert listening, f"Failed to start echo server on port {echoPort}"

        try:
            # Start monitoring server ports before triggering failover
            serverPorts = [
                portConfig.serverToClientTun1ListenPort,
                portConfig.serverToClientTun2ListenPort,
            ]

            # Wait for server ports to be available before proceeding
            from util_socket_methods import (
                waitForCondition,
                waitForPortsOpenCallable,
            )

            logger.info("Waiting for server ports to be available...")
            portsAvailable, _ = await waitForCondition(
                waitForPortsOpenCallable("server", serverPorts),
                30,  # 30 second timeout
                1.0,  # Check every second
                description="Server ports availability",
            )
            assert (
                portsAvailable
            ), f"Server ports {serverPorts} not available within 30 seconds"

            # Trigger failover to client1
            tunnelPort = portConfig.client1ToServerTun1ListenPort
            conn = UtilTcpSocket("timing_trigger_client1")
            connected = await conn.startConnect("client1", tunnelPort)
            assert connected, f"Failed to connect to client1:{tunnelPort}"

            # Send first data to trigger failover and close immediately
            await conn.write(b"TRIGGER")
            await conn.close()

            # Monitor server ports - they should close within 1 second
            startTime = time.time()
            allClosed = False

            while (time.time() - startTime) < 5.0:  # Give 5 seconds max
                closedPorts = []
                for port in serverPorts:
                    if not checkPortOpen("server", port, timeout=0.1):
                        closedPorts.append(port)

                if len(closedPorts) == len(serverPorts):
                    closeTime = time.time() - startTime
                    allClosed = True
                    logger.info(
                        f"Test 2.6: All server ports closed after {closeTime:.2f}s"
                    )
                    assert (
                        closeTime <= 1.0
                    ), f"Server ports took {closeTime:.2f}s to close (expected ≤1s)"
                    break

                await asyncio.sleep(0.1)

            assert allClosed, "Server ports did not close within expected time"

            # Monitor server ports - they should reopen at configured timeout
            expectedTimeout = portConfig.reconnectTimeoutSecs
            startReopenTime = time.time()
            allReopened = False

            while (time.time() - startReopenTime) < (expectedTimeout + 5):
                openPorts = []
                for port in serverPorts:
                    if checkPortOpen("server", port, timeout=0.1):
                        openPorts.append(port)

                if len(openPorts) == len(serverPorts):
                    reopenTime = time.time() - startReopenTime
                    allReopened = True
                    logger.info(
                        f"Test 2.6: All server ports reopened after {reopenTime:.2f}s (expected around {expectedTimeout}s)"
                    )
                    break

                await asyncio.sleep(0.5)

            assert (
                allReopened
            ), f"Server ports did not reopen within expected time range"
            logger.info(
                "Test 2.6: Successfully validated server port closure and reopen timing during failover to client 1"
            )

        finally:
            await echoServer.close()

    @pytest.mark.asyncio
    async def test_2_7_server_port_closure_timing_client2_second(self):
        """Test 2.7: Primary Server Port Closure Timing During Failover to Client 2 (Second)"""
        portConfig = get_port_config()

        # Start echo server for client2 tunnel
        echoPort = portConfig.clientToServerTun1ConnectPort
        echoServer = UtilTcpSocket(
            "echo_timing_client2_2nd", shouldEchoData=True
        )
        listening = await echoServer.startListen(port=echoPort, host="0.0.0.0")
        assert listening, f"Failed to start echo server on port {echoPort}"

        try:
            # Start monitoring server ports before triggering failover
            serverPorts = [
                portConfig.serverToClientTun1ListenPort,
                portConfig.serverToClientTun2ListenPort,
            ]

            # Wait for server ports to be available before proceeding
            from util_socket_methods import (
                waitForCondition,
                waitForPortsOpenCallable,
            )

            logger.info("Waiting for server ports to be available...")
            portsAvailable, _ = await waitForCondition(
                waitForPortsOpenCallable("server", serverPorts),
                30,  # 30 second timeout
                1.0,  # Check every second
                description="Server ports availability",
            )
            assert (
                portsAvailable
            ), f"Server ports {serverPorts} not available within 30 seconds"

            # Trigger failover to client2
            tunnelPort = portConfig.client2ToServerTun1ListenPort
            conn = UtilTcpSocket("timing_trigger_client2_2nd")
            connected = await conn.startConnect("client2", tunnelPort)
            assert connected, f"Failed to connect to client2:{tunnelPort}"

            # Send first data to trigger failover and close immediately
            await conn.write(b"TRIGGER")
            await conn.close()

            # Monitor server ports - they should close within 1 second
            startTime = time.time()
            allClosed = False

            while (time.time() - startTime) < 5.0:  # Give 5 seconds max
                closedPorts = []
                for port in serverPorts:
                    if not checkPortOpen("server", port, timeout=0.1):
                        closedPorts.append(port)

                if len(closedPorts) == len(serverPorts):
                    closeTime = time.time() - startTime
                    allClosed = True
                    logger.info(
                        f"Test 2.7: All server ports closed after {closeTime:.2f}s"
                    )
                    assert (
                        closeTime <= 1.0
                    ), f"Server ports took {closeTime:.2f}s to close (expected ≤1s)"
                    break

                await asyncio.sleep(0.1)

            assert allClosed, "Server ports did not close within expected time"

            # Monitor server ports - they should reopen at configured timeout
            expectedTimeout = portConfig.reconnectTimeoutSecs
            startReopenTime = time.time()
            allReopened = False

            while (time.time() - startReopenTime) < (expectedTimeout + 5):
                openPorts = []
                for port in serverPorts:
                    if checkPortOpen("server", port, timeout=0.1):
                        openPorts.append(port)

                if len(openPorts) == len(serverPorts):
                    reopenTime = time.time() - startReopenTime
                    allReopened = True
                    logger.info(
                        f"Test 2.7: All server ports reopened after {reopenTime:.2f}s (expected around {expectedTimeout}s)"
                    )
                    break

                await asyncio.sleep(0.5)

            assert (
                allReopened
            ), f"Server ports did not reopen within expected time range"
            logger.info(
                "Test 2.7: Successfully validated server port closure and reopen timing during failover to client 2 (second)"
            )

        finally:
            await echoServer.close()

    @pytest.mark.asyncio
    async def test_2_8_server_port_closure_timing_client1_second(self):
        """Test 2.8: Primary Server Port Closure Timing During Failover to Client 1 (Second)"""
        portConfig = get_port_config()

        # Start echo server for client1 tunnel
        echoPort = portConfig.clientToServerTun1ConnectPort
        echoServer = UtilTcpSocket(
            "echo_timing_client1_2nd", shouldEchoData=True
        )
        listening = await echoServer.startListen(port=echoPort, host="0.0.0.0")
        assert listening, f"Failed to start echo server on port {echoPort}"

        try:
            # Start monitoring server ports before triggering failover
            serverPorts = [
                portConfig.serverToClientTun1ListenPort,
                portConfig.serverToClientTun2ListenPort,
            ]

            # Wait for server ports to be available before proceeding
            from util_socket_methods import (
                waitForCondition,
                waitForPortsOpenCallable,
            )

            logger.info("Waiting for server ports to be available...")
            portsAvailable, _ = await waitForCondition(
                waitForPortsOpenCallable("server", serverPorts),
                30,  # 30 second timeout
                1.0,  # Check every second
                description="Server ports availability",
            )
            assert (
                portsAvailable
            ), f"Server ports {serverPorts} not available within 30 seconds"

            # Trigger failover to client1
            tunnelPort = portConfig.client1ToServerTun1ListenPort
            conn = UtilTcpSocket("timing_trigger_client1_2nd")
            connected = await conn.startConnect("client1", tunnelPort)
            assert connected, f"Failed to connect to client1:{tunnelPort}"

            # Send first data to trigger failover and close immediately
            await conn.write(b"TRIGGER")
            await conn.close()

            # Monitor server ports - they should close within 1 second
            startTime = time.time()
            allClosed = False

            while (time.time() - startTime) < 5.0:  # Give 5 seconds max
                closedPorts = []
                for port in serverPorts:
                    if not checkPortOpen("server", port, timeout=0.1):
                        closedPorts.append(port)

                if len(closedPorts) == len(serverPorts):
                    closeTime = time.time() - startTime
                    allClosed = True
                    logger.info(
                        f"Test 2.8: All server ports closed after {closeTime:.2f}s"
                    )
                    assert (
                        closeTime <= 1.0
                    ), f"Server ports took {closeTime:.2f}s to close (expected ≤1s)"
                    break

                await asyncio.sleep(0.1)

            assert allClosed, "Server ports did not close within expected time"

            # Monitor server ports - they should reopen at configured timeout
            expectedTimeout = portConfig.reconnectTimeoutSecs
            startReopenTime = time.time()
            allReopened = False

            while (time.time() - startReopenTime) < (expectedTimeout + 5):
                openPorts = []
                for port in serverPorts:
                    if checkPortOpen("server", port, timeout=0.1):
                        openPorts.append(port)

                if len(openPorts) == len(serverPorts):
                    reopenTime = time.time() - startReopenTime
                    allReopened = True
                    logger.info(
                        f"Test 2.8: All server ports reopened after {reopenTime:.2f}s (expected around {expectedTimeout}s)"
                    )
                    break

                await asyncio.sleep(0.5)

            assert (
                allReopened
            ), f"Server ports did not reopen within expected time range"
            logger.info(
                "Test 2.8: Successfully validated server port closure and reopen timing during failover to client 1 (second)"
            )

        finally:
            await echoServer.close()

    @pytest.mark.asyncio
    async def test_2_9_standby_port_closure_timing_client2_failover(self):
        """Test 2.9: New Standby Port Closure Timing During Failover to Client 2"""
        portConfig = get_port_config()

        # Start echo server for client2 tunnel
        echoPort = portConfig.clientToServerTun1ConnectPort
        echoServer = UtilTcpSocket(
            "echo_standby_timing_client2", shouldEchoData=True
        )
        listening = await echoServer.startListen(port=echoPort, host="0.0.0.0")
        assert listening, f"Failed to start echo server on port {echoPort}"

        try:
            # Monitor client1 ports (will become new standby after failover)
            client1Ports = [
                portConfig.client1ToServerTun1ListenPort,
                portConfig.client1ToServerTun2ListenPort,
            ]

            # Wait for client1 ports to be available before proceeding
            from util_socket_methods import (
                waitForCondition,
                waitForPortsOpenCallable,
            )

            logger.info("Waiting for client1 ports to be available...")
            portsAvailable, _ = await waitForCondition(
                waitForPortsOpenCallable("client1", client1Ports),
                30,  # 30 second timeout
                1.0,  # Check every second
                description="Client1 ports availability",
            )
            assert (
                portsAvailable
            ), f"Client1 ports {client1Ports} not available within 30 seconds"

            # Trigger failover to client2
            tunnelPort = portConfig.client2ToServerTun1ListenPort
            conn = UtilTcpSocket("standby_timing_trigger_client2")
            connected = await conn.startConnect("client2", tunnelPort)
            assert connected, f"Failed to connect to client2:{tunnelPort}"

            # Send first data to trigger failover and close immediately
            await conn.write(b"TRIGGER")
            await conn.close()

            # Monitor client1 ports - they should close within 1 second (becoming new standby)
            startTime = time.time()
            allClosed = False

            while (time.time() - startTime) < 5.0:  # Give 5 seconds max
                closedPorts = []
                for port in client1Ports:
                    if not checkPortOpen("client1", port, timeout=0.1):
                        closedPorts.append(port)

                if len(closedPorts) == len(client1Ports):
                    closeTime = time.time() - startTime
                    allClosed = True
                    logger.info(
                        f"Test 2.9: All client1 standby ports closed after {closeTime:.2f}s"
                    )
                    assert (
                        closeTime <= 1.0
                    ), f"Client1 standby ports took {closeTime:.2f}s to close (expected ≤1s)"
                    break

                await asyncio.sleep(0.1)

            assert (
                allClosed
            ), "Client1 standby ports did not close within expected time"

            # Monitor client1 ports - they should reopen at configured timeout
            expectedTimeout = portConfig.reconnectTimeoutSecs
            startReopenTime = time.time()
            allReopened = False

            while (time.time() - startReopenTime) < (expectedTimeout + 5):
                openPorts = []
                for port in client1Ports:
                    if checkPortOpen("client1", port, timeout=0.1):
                        openPorts.append(port)

                if len(openPorts) == len(client1Ports):
                    reopenTime = time.time() - startReopenTime
                    allReopened = True
                    logger.info(
                        f"Test 2.9: All client1 standby ports reopened after {reopenTime:.2f}s (expected around {expectedTimeout}s)"
                    )
                    break

                await asyncio.sleep(0.5)

            assert (
                allReopened
            ), f"Client1 standby ports did not reopen within expected time range"
            logger.info(
                "Test 2.9: Successfully validated standby port closure and reopen timing during failover to client 2"
            )

        finally:
            await echoServer.close()

    @pytest.mark.asyncio
    async def test_2_10_standby_port_closure_timing_client1_failover(self):
        """Test 2.10: New Standby Port Closure Timing During Failover to Client 1"""
        portConfig = get_port_config()

        # Start echo server for client1 tunnel
        echoPort = portConfig.clientToServerTun1ConnectPort
        echoServer = UtilTcpSocket(
            "echo_standby_timing_client1", shouldEchoData=True
        )
        listening = await echoServer.startListen(port=echoPort, host="0.0.0.0")
        assert listening, f"Failed to start echo server on port {echoPort}"

        try:
            # Monitor client2 ports (will become new standby after failover)
            client2Ports = [
                portConfig.client2ToServerTun1ListenPort,
                portConfig.client2ToServerTun2ListenPort,
            ]

            # Wait for client2 ports to be available before proceeding
            from util_socket_methods import (
                waitForCondition,
                waitForPortsOpenCallable,
            )

            logger.info("Waiting for client2 ports to be available...")
            portsAvailable, _ = await waitForCondition(
                waitForPortsOpenCallable("client2", client2Ports),
                30,  # 30 second timeout
                1.0,  # Check every second
                description="Client2 ports availability",
            )
            assert (
                portsAvailable
            ), f"Client2 ports {client2Ports} not available within 30 seconds"

            # Trigger failover to client1
            tunnelPort = portConfig.client1ToServerTun1ListenPort
            conn = UtilTcpSocket("standby_timing_trigger_client1")
            connected = await conn.startConnect("client1", tunnelPort)
            assert connected, f"Failed to connect to client1:{tunnelPort}"

            # Send first data to trigger failover and close immediately
            await conn.write(b"TRIGGER")
            await conn.close()

            # Monitor client2 ports - they should close within 1 second (becoming new standby)
            startTime = time.time()
            allClosed = False

            while (time.time() - startTime) < 5.0:  # Give 5 seconds max
                closedPorts = []
                for port in client2Ports:
                    if not checkPortOpen("client2", port, timeout=0.1):
                        closedPorts.append(port)

                if len(closedPorts) == len(client2Ports):
                    closeTime = time.time() - startTime
                    allClosed = True
                    logger.info(
                        f"Test 2.10: All client2 standby ports closed after {closeTime:.2f}s"
                    )
                    assert (
                        closeTime <= 1.0
                    ), f"Client2 standby ports took {closeTime:.2f}s to close (expected ≤1s)"
                    break

                await asyncio.sleep(0.1)

            assert (
                allClosed
            ), "Client2 standby ports did not close within expected time"

            # Monitor client2 ports - they should reopen at configured timeout
            expectedTimeout = portConfig.reconnectTimeoutSecs
            startReopenTime = time.time()
            allReopened = False

            while (time.time() - startReopenTime) < (expectedTimeout + 5):
                openPorts = []
                for port in client2Ports:
                    if checkPortOpen("client2", port, timeout=0.1):
                        openPorts.append(port)

                if len(openPorts) == len(client2Ports):
                    reopenTime = time.time() - startReopenTime
                    allReopened = True
                    logger.info(
                        f"Test 2.10: All client2 standby ports reopened after {reopenTime:.2f}s (expected around {expectedTimeout}s)"
                    )
                    break

                await asyncio.sleep(0.5)

            assert (
                allReopened
            ), f"Client2 standby ports did not reopen within expected time range"
            logger.info(
                "Test 2.10: Successfully validated standby port closure and reopen timing during failover to client 1"
            )

        finally:
            await echoServer.close()

    @pytest.mark.asyncio
    async def test_2_11_standby_port_closure_timing_client2_second(self):
        """Test 2.11: New Standby Port Closure Timing During Failover to Client 2 (Second)"""
        portConfig = get_port_config()

        # Start echo server for client2 tunnel
        echoPort = portConfig.clientToServerTun1ConnectPort
        echoServer = UtilTcpSocket(
            "echo_standby_timing_client2_2nd", shouldEchoData=True
        )
        listening = await echoServer.startListen(port=echoPort, host="0.0.0.0")
        assert listening, f"Failed to start echo server on port {echoPort}"

        try:
            # Monitor client1 ports (will become new standby after failover)
            client1Ports = [
                portConfig.client1ToServerTun1ListenPort,
                portConfig.client1ToServerTun2ListenPort,
            ]

            # Wait for client1 ports to be available before proceeding
            from util_socket_methods import (
                waitForCondition,
                waitForPortsOpenCallable,
            )

            logger.info("Waiting for client1 ports to be available...")
            portsAvailable, _ = await waitForCondition(
                waitForPortsOpenCallable("client1", client1Ports),
                30,  # 30 second timeout
                1.0,  # Check every second
                description="Client1 ports availability",
            )
            assert (
                portsAvailable
            ), f"Client1 ports {client1Ports} not available within 30 seconds"

            # Trigger failover to client2
            tunnelPort = portConfig.client2ToServerTun1ListenPort
            conn = UtilTcpSocket("standby_timing_trigger_client2_2nd")
            connected = await conn.startConnect("client2", tunnelPort)
            assert connected, f"Failed to connect to client2:{tunnelPort}"

            # Send first data to trigger failover and close immediately
            await conn.write(b"TRIGGER")
            await conn.close()

            # Monitor client1 ports - they should close within 1 second (becoming new standby)
            startTime = time.time()
            allClosed = False

            while (time.time() - startTime) < 5.0:  # Give 5 seconds max
                closedPorts = []
                for port in client1Ports:
                    if not checkPortOpen("client1", port, timeout=0.1):
                        closedPorts.append(port)

                if len(closedPorts) == len(client1Ports):
                    closeTime = time.time() - startTime
                    allClosed = True
                    logger.info(
                        f"Test 2.11: All client1 standby ports closed after {closeTime:.2f}s"
                    )
                    assert (
                        closeTime <= 1.0
                    ), f"Client1 standby ports took {closeTime:.2f}s to close (expected ≤1s)"
                    break

                await asyncio.sleep(0.1)

            assert (
                allClosed
            ), "Client1 standby ports did not close within expected time"

            # Monitor client1 ports - they should reopen at configured timeout
            expectedTimeout = portConfig.reconnectTimeoutSecs
            startReopenTime = time.time()
            allReopened = False

            while (time.time() - startReopenTime) < (expectedTimeout + 5):
                openPorts = []
                for port in client1Ports:
                    if checkPortOpen("client1", port, timeout=0.1):
                        openPorts.append(port)

                if len(openPorts) == len(client1Ports):
                    reopenTime = time.time() - startReopenTime
                    allReopened = True
                    logger.info(
                        f"Test 2.11: All client1 standby ports reopened after {reopenTime:.2f}s (expected around {expectedTimeout}s)"
                    )
                    break

                await asyncio.sleep(0.5)

            assert (
                allReopened
            ), f"Client1 standby ports did not reopen within expected time range"
            logger.info(
                "Test 2.11: Successfully validated standby port closure and reopen timing during failover to client 2 (second)"
            )

        finally:
            await echoServer.close()

    @pytest.mark.asyncio
    async def test_2_12_standby_port_closure_timing_client1_second(self):
        """Test 2.12: New Standby Port Closure Timing During Failover to Client 1 (Second)"""
        portConfig = get_port_config()

        # Start echo server for client1 tunnel
        echoPort = portConfig.clientToServerTun1ConnectPort
        echoServer = UtilTcpSocket(
            "echo_standby_timing_client1_2nd", shouldEchoData=True
        )
        listening = await echoServer.startListen(port=echoPort, host="0.0.0.0")
        assert listening, f"Failed to start echo server on port {echoPort}"

        try:
            # Monitor client2 ports (will become new standby after failover)
            client2Ports = [
                portConfig.client2ToServerTun1ListenPort,
                portConfig.client2ToServerTun2ListenPort,
            ]

            # Wait for client2 ports to be available before proceeding
            from util_socket_methods import (
                waitForCondition,
                waitForPortsOpenCallable,
            )

            logger.info("Waiting for client2 ports to be available...")
            portsAvailable, _ = await waitForCondition(
                waitForPortsOpenCallable("client2", client2Ports),
                30,  # 30 second timeout
                1.0,  # Check every second
                description="Client2 ports availability",
            )
            assert (
                portsAvailable
            ), f"Client2 ports {client2Ports} not available within 30 seconds"

            # Trigger failover to client1
            tunnelPort = portConfig.client1ToServerTun1ListenPort
            conn = UtilTcpSocket("standby_timing_trigger_client1_2nd")
            connected = await conn.startConnect("client1", tunnelPort)
            assert connected, f"Failed to connect to client1:{tunnelPort}"

            # Send first data to trigger failover and close immediately
            await conn.write(b"TRIGGER")
            await conn.close()

            # Monitor client2 ports - they should close within 1 second (becoming new standby)
            startTime = time.time()
            allClosed = False

            while (time.time() - startTime) < 5.0:  # Give 5 seconds max
                closedPorts = []
                for port in client2Ports:
                    if not checkPortOpen("client2", port, timeout=0.1):
                        closedPorts.append(port)

                if len(closedPorts) == len(client2Ports):
                    closeTime = time.time() - startTime
                    allClosed = True
                    logger.info(
                        f"Test 2.12: All client2 standby ports closed after {closeTime:.2f}s"
                    )
                    assert (
                        closeTime <= 1.0
                    ), f"Client2 standby ports took {closeTime:.2f}s to close (expected ≤1s)"
                    break

                await asyncio.sleep(0.1)

            assert (
                allClosed
            ), "Client2 standby ports did not close within expected time"

            # Monitor client2 ports - they should reopen at configured timeout
            expectedTimeout = portConfig.reconnectTimeoutSecs
            startReopenTime = time.time()
            allReopened = False

            while (time.time() - startReopenTime) < (expectedTimeout + 5):
                openPorts = []
                for port in client2Ports:
                    if checkPortOpen("client2", port, timeout=0.1):
                        openPorts.append(port)

                if len(openPorts) == len(client2Ports):
                    reopenTime = time.time() - startReopenTime
                    allReopened = True
                    logger.info(
                        f"Test 2.12: All client2 standby ports reopened after {reopenTime:.2f}s (expected around {expectedTimeout}s)"
                    )
                    break

                await asyncio.sleep(0.5)

            assert (
                allReopened
            ), f"Client2 standby ports did not reopen within expected time range"
            logger.info(
                "Test 2.12: Successfully validated standby port closure and reopen timing during failover to client 1 (second)"
            )

        finally:
            await echoServer.close()

    @pytest.mark.asyncio
    async def test_2_13_final_functional_validation(self):
        """Test 2.13: Final Functional Validation"""
        portConfig = get_port_config()

        # Reset to ensure we're back to client1 as active
        await resetActiveClient()

        # Start echo servers for both client tunnels
        echoPortClient = portConfig.clientToServerTun1ConnectPort
        echoServerClient = UtilTcpSocket(
            "echo_final_client", shouldEchoData=True
        )
        listeningClient = await echoServerClient.startListen(
            port=echoPortClient, host="0.0.0.0"
        )
        assert (
            listeningClient
        ), f"Failed to start client echo server on port {echoPortClient}"

        echoPortServer = portConfig.serverToClient1Tun1ConnectPort
        echoServerServer = UtilTcpSocket(
            "echo_final_server", shouldEchoData=True
        )
        listeningServer = await echoServerServer.startListen(
            port=echoPortServer, host="0.0.0.0"
        )
        assert (
            listeningServer
        ), f"Failed to start server echo server on port {echoPortServer}"

        try:
            # Test client-to-server tunnel
            clientTunnelPort = portConfig.client1ToServerTun1ListenPort
            clientConn = UtilTcpSocket("final_client_test")
            clientConnected = await clientConn.startConnect(
                "client1", clientTunnelPort
            )
            assert (
                clientConnected
            ), f"Failed to connect to client1:{clientTunnelPort}"

            testData = b"FINAL_CLIENT_TEST"
            receivedData, success = await clientConn.sendDataExpectEcho(
                testData
            )
            await clientConn.close()

            assert success, "Failed to send/receive on client-to-server tunnel"
            assert (
                receivedData == testData
            ), "Data mismatch on client-to-server tunnel"

            # Test server-to-client tunnel
            serverTunnelPort = portConfig.serverToClientTun1ListenPort
            serverConn = UtilTcpSocket("final_server_test")
            serverConnected = await serverConn.startConnect(
                "server", serverTunnelPort
            )
            assert (
                serverConnected
            ), f"Failed to connect to server:{serverTunnelPort}"

            testData = b"FINAL_SERVER_TEST"
            receivedData, success = await serverConn.sendDataExpectEcho(
                testData
            )
            await serverConn.close()

            assert success, "Failed to send/receive on server-to-client tunnel"
            assert (
                receivedData == testData
            ), "Data mismatch on server-to-client tunnel"

            logger.info(
                "Test 2.13: Successfully completed final functional validation"
            )

        finally:
            await echoServerClient.close()
            await echoServerServer.close()
