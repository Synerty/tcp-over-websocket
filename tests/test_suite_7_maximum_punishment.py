import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
import logging
import time
import random

import pytest

from util_socket_methods import (
    resetActiveClient,
    triggerFailoverToClient2,
    triggerFailoverBackToClient1,
)
from util_port_config import get_port_config
from util_tcp_socket import UtilTcpSocket
from tests.util_data_send_ensure_receive_connection import (
    UtilDataSendEnsureReceivedConnection,
)
from util_data_methods import generateDeterministicData, calculateSha256

logger = logging.getLogger(__name__)


def generateTransferSizes(count: int, minSize: int, maxSize: int) -> list[int]:
    """Generate a list of random transfer sizes with weighted distribution"""
    sizes = []

    # Size ranges with weights (more smaller transfers)
    ranges = [
        (100 * 1024, 500 * 1024, 40),  # 100KB-500KB (40%)
        (500 * 1024, 1 * 1024 * 1024, 25),  # 500KB-1MB (25%)
        (1 * 1024 * 1024, 5 * 1024 * 1024, 20),  # 1MB-5MB (20%)
        (5 * 1024 * 1024, 20 * 1024 * 1024, 10),  # 5MB-20MB (10%)
        (20 * 1024 * 1024, maxSize, 5),  # 20MB-250MB (5%)
    ]

    for rangeMin, rangeMax, weight in ranges:
        numInRange = int(count * weight / 100)
        for _ in range(numInRange):
            sizes.append(random.randint(rangeMin, min(rangeMax, maxSize)))

    # Fill remaining to reach exact count
    while len(sizes) < count:
        sizes.append(random.randint(minSize, maxSize))

    random.shuffle(sizes)
    return sizes[:count]


class TestMaximumPunishment:
    """Test Suite 6: Maximum Punishment - 100 concurrent connections with 20 max concurrency"""

    @pytest.mark.asyncio
    async def test_0_0_reset_active_client(self):
        """Test 0.0: Reset Active Client"""
        await resetActiveClient()

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_7_1_100_concurrent_transfers_client_to_server_tun1(self):
        """Test 7.1: 100 Concurrent Transfers - Client-to-Server Tunnel 1"""
        portConfig = get_port_config()

        numConnections = 100
        maxConcurrency = 20
        transferSizes = generateTransferSizes(
            numConnections, 100 * 1024, 250 * 1024 * 1024
        )

        totalDataSize = sum(transferSizes)
        logger.info(
            f"Test 7.1: {numConnections} connections, total data: {totalDataSize / (1024 * 1024):.1f}MB"
        )

        # Start echo server
        echoPort = portConfig.clientToServerTun1ConnectPort
        echoServer = UtilTcpSocket(
            "echo_backend_6_1",
            shouldEchoData=True,
            logTrafficEvents=False,
        )
        listening = await echoServer.startListen(port=echoPort, host="0.0.0.0")
        assert listening, f"Failed to start echo server on port {echoPort}"

        try:
            tunnelPort = portConfig.client1ToServerTun1ListenPort

            # Create all connections upfront
            connections = []
            for i in range(numConnections):
                conn = UtilTcpSocket(
                    f"test_7_1_conn_{i}", logTrafficEvents=False
                )
                connected = await conn.startConnect("client1", tunnelPort)
                if not connected:
                    logger.warning(
                        f"Test 7.1: Connection {i} failed to connect"
                    )
                    await conn.close()
                    continue
                connections.append(conn)

            logger.info(
                f"Test 7.1: {len(connections)}/{numConnections} connections established"
            )

            try:
                # Generate test data and create transfers
                transfers = []
                for i, (conn, size) in enumerate(
                    zip(connections, transferSizes)
                ):
                    testData = generateDeterministicData(size, seed=6001 + i)
                    transfer = UtilDataSendEnsureReceivedConnection(
                        f"transfer_{i}", testData, timeout=600.0
                    )
                    transfer.setConnection(conn)
                    transfers.append(transfer)

                # Run transfers with concurrency limit
                semaphore = asyncio.Semaphore(maxConcurrency)

                async def limitedTransfer(transfer):
                    async with semaphore:
                        return await transfer.executeTransfer()

                startTime = time.time()
                results = await asyncio.gather(
                    *[limitedTransfer(t) for t in transfers]
                )
                endTime = time.time()

                # Validate results
                successCount = 0
                validatedCount = 0
                totalThroughput = 0

                for i, (success, receivedData, throughput) in enumerate(
                    results
                ):
                    transfer = transfers[i]
                    size = transferSizes[i]

                    if not success:
                        logger.warning(
                            f"Test 7.1: Transfer {i} ({size / (1024 * 1024):.2f}MB) failed"
                        )
                        continue

                    if len(receivedData) != len(transfer.data):
                        logger.warning(
                            f"Test 7.1: Transfer {i} size mismatch: expected {len(transfer.data)}, got {len(receivedData)}"
                        )
                        continue

                    # Validate data content matches
                    if receivedData != transfer.data:
                        logger.warning(
                            f"Test 7.1: Transfer {i} data content mismatch"
                        )
                        continue

                    successCount += 1

                    # Only validate checksums for transfers 5MB or smaller
                    if size <= 5 * 1024 * 1024:
                        expectedChecksum = calculateSha256(transfer.data)
                        actualChecksum = calculateSha256(receivedData)
                        if actualChecksum != expectedChecksum:
                            logger.warning(
                                f"Test 7.1: Transfer {i} checksum mismatch"
                            )
                            continue
                        validatedCount += 1

                    totalThroughput += throughput

                duration = endTime - startTime
                overallThroughput = (
                    (totalDataSize * 2) / (1024 * 1024)
                ) / duration

                logger.info(
                    f"Test 7.1: {successCount}/{len(transfers)} transfers successful"
                )
                logger.info(
                    f"Test 7.1: {validatedCount} transfers checksum-validated (≤5MB)"
                )
                logger.info(f"Test 7.1: Duration: {duration:.1f}s")
                logger.info(
                    f"Test 7.1: Overall throughput: {overallThroughput:.2f} MB/s (bidirectional)"
                )

                assert (
                    successCount >= 100
                ), f"Only {successCount}/{len(transfers)} transfers succeeded"

            finally:
                for conn in connections:
                    await conn.close()
        finally:
            await echoServer.close()

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_7_2_100_concurrent_transfers_server_to_client_tun1(self):
        """Test 7.2: 100 Concurrent Transfers - Server-to-Client Tunnel 1"""
        portConfig = get_port_config()

        numConnections = 100
        maxConcurrency = 20
        transferSizes = generateTransferSizes(
            numConnections, 100 * 1024, 250 * 1024 * 1024
        )

        totalDataSize = sum(transferSizes)
        logger.info(
            f"Test 7.2: {numConnections} connections, total data: {totalDataSize / (1024 * 1024):.1f}MB"
        )

        # Start echo server
        echoPort = portConfig.serverToClient1Tun1ConnectPort
        echoServer = UtilTcpSocket(
            "echo_backend_6_2",
            shouldEchoData=True,
            logTrafficEvents=False,
        )
        listening = await echoServer.startListen(port=echoPort, host="0.0.0.0")
        assert listening, f"Failed to start echo server on port {echoPort}"

        try:
            tunnelPort = portConfig.serverToClientTun1ListenPort

            # Create all connections upfront
            connections = []
            for i in range(numConnections):
                conn = UtilTcpSocket(
                    f"test_7_2_conn_{i}", logTrafficEvents=False
                )
                connected = await conn.startConnect("server", tunnelPort)
                if not connected:
                    logger.warning(
                        f"Test 7.2: Connection {i} failed to connect"
                    )
                    await conn.close()
                    continue
                connections.append(conn)

            logger.info(
                f"Test 7.2: {len(connections)}/{numConnections} connections established"
            )

            try:
                # Generate test data and create transfers
                transfers = []
                for i, (conn, size) in enumerate(
                    zip(connections, transferSizes)
                ):
                    testData = generateDeterministicData(size, seed=6002 + i)
                    transfer = UtilDataSendEnsureReceivedConnection(
                        f"transfer_{i}", testData, timeout=600.0
                    )
                    transfer.setConnection(conn)
                    transfers.append(transfer)

                # Run transfers with concurrency limit
                semaphore = asyncio.Semaphore(maxConcurrency)

                async def limitedTransfer(transfer):
                    async with semaphore:
                        return await transfer.executeTransfer()

                startTime = time.time()
                results = await asyncio.gather(
                    *[limitedTransfer(t) for t in transfers]
                )
                endTime = time.time()

                # Validate results
                successCount = 0
                validatedCount = 0
                totalThroughput = 0

                for i, (success, receivedData, throughput) in enumerate(
                    results
                ):
                    transfer = transfers[i]
                    size = transferSizes[i]

                    if not success:
                        logger.warning(
                            f"Test 7.2: Transfer {i} ({size / (1024 * 1024):.2f}MB) failed"
                        )
                        continue

                    if len(receivedData) != len(transfer.data):
                        logger.warning(
                            f"Test 7.2: Transfer {i} size mismatch: expected {len(transfer.data)}, got {len(receivedData)}"
                        )
                        continue

                    # Validate data content matches
                    if receivedData != transfer.data:
                        logger.warning(
                            f"Test 7.2: Transfer {i} data content mismatch"
                        )
                        continue

                    successCount += 1

                    # Only validate checksums for transfers 5MB or smaller
                    if size <= 5 * 1024 * 1024:
                        expectedChecksum = calculateSha256(transfer.data)
                        actualChecksum = calculateSha256(receivedData)
                        if actualChecksum != expectedChecksum:
                            logger.warning(
                                f"Test 7.2: Transfer {i} checksum mismatch"
                            )
                            continue
                        validatedCount += 1

                    totalThroughput += throughput

                duration = endTime - startTime
                overallThroughput = (
                    (totalDataSize * 2) / (1024 * 1024)
                ) / duration

                logger.info(
                    f"Test 7.2: {successCount}/{len(transfers)} transfers successful"
                )
                logger.info(
                    f"Test 7.2: {validatedCount} transfers checksum-validated (≤5MB)"
                )
                logger.info(f"Test 7.2: Duration: {duration:.1f}s")
                logger.info(
                    f"Test 7.2: Overall throughput: {overallThroughput:.2f} MB/s (bidirectional)"
                )

                assert (
                    successCount >= 100
                ), f"Only {successCount}/{len(transfers)} transfers succeeded"

            finally:
                for conn in connections:
                    await conn.close()
        finally:
            await echoServer.close()

    @pytest.mark.asyncio
    async def test_7_3_failover_event(self):
        """Test 7.3: Failover Event"""
        await triggerFailoverToClient2()

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_7_4_100_concurrent_transfers_client_to_server_tun1_client2(
        self,
    ):
        """Test 7.4: 100 Concurrent Transfers - Client-to-Server Tunnel 1 (Client 2)"""
        portConfig = get_port_config()

        numConnections = 100
        maxConcurrency = 20
        transferSizes = generateTransferSizes(
            numConnections, 100 * 1024, 250 * 1024 * 1024
        )

        totalDataSize = sum(transferSizes)
        logger.info(
            f"Test 7.4: {numConnections} connections, total data: {totalDataSize / (1024 * 1024):.1f}MB"
        )

        # Start echo server
        echoPort = portConfig.clientToServerTun1ConnectPort
        echoServer = UtilTcpSocket(
            "echo_backend_6_4",
            shouldEchoData=True,
            logTrafficEvents=False,
        )
        listening = await echoServer.startListen(port=echoPort, host="0.0.0.0")
        assert listening, f"Failed to start echo server on port {echoPort}"

        try:
            tunnelPort = portConfig.client2ToServerTun1ListenPort

            # Create all connections upfront
            connections = []
            for i in range(numConnections):
                conn = UtilTcpSocket(
                    f"test_7_4_conn_{i}", logTrafficEvents=False
                )
                connected = await conn.startConnect("client2", tunnelPort)
                if not connected:
                    logger.warning(
                        f"Test 7.4: Connection {i} failed to connect"
                    )
                    await conn.close()
                    continue
                connections.append(conn)

            logger.info(
                f"Test 7.4: {len(connections)}/{numConnections} connections established"
            )

            try:
                # Generate test data and create transfers
                transfers = []
                for i, (conn, size) in enumerate(
                    zip(connections, transferSizes)
                ):
                    testData = generateDeterministicData(size, seed=6004 + i)
                    transfer = UtilDataSendEnsureReceivedConnection(
                        f"transfer_{i}", testData, timeout=600.0
                    )
                    transfer.setConnection(conn)
                    transfers.append(transfer)

                # Run transfers with concurrency limit
                semaphore = asyncio.Semaphore(maxConcurrency)

                async def limitedTransfer(transfer):
                    async with semaphore:
                        return await transfer.executeTransfer()

                startTime = time.time()
                results = await asyncio.gather(
                    *[limitedTransfer(t) for t in transfers]
                )
                endTime = time.time()

                # Validate results
                successCount = 0
                validatedCount = 0
                totalThroughput = 0

                for i, (success, receivedData, throughput) in enumerate(
                    results
                ):
                    transfer = transfers[i]
                    size = transferSizes[i]

                    if not success:
                        logger.warning(
                            f"Test 7.4: Transfer {i} ({size / (1024 * 1024):.2f}MB) failed"
                        )
                        continue

                    if len(receivedData) != len(transfer.data):
                        logger.warning(
                            f"Test 7.4: Transfer {i} size mismatch: expected {len(transfer.data)}, got {len(receivedData)}"
                        )
                        continue

                    # Validate data content matches
                    if receivedData != transfer.data:
                        logger.warning(
                            f"Test 7.4: Transfer {i} data content mismatch"
                        )
                        continue

                    successCount += 1

                    # Only validate checksums for transfers 5MB or smaller
                    if size <= 5 * 1024 * 1024:
                        expectedChecksum = calculateSha256(transfer.data)
                        actualChecksum = calculateSha256(receivedData)
                        if actualChecksum != expectedChecksum:
                            logger.warning(
                                f"Test 7.4: Transfer {i} checksum mismatch"
                            )
                            continue
                        validatedCount += 1

                    totalThroughput += throughput

                duration = endTime - startTime
                overallThroughput = (
                    (totalDataSize * 2) / (1024 * 1024)
                ) / duration

                logger.info(
                    f"Test 7.4: {successCount}/{len(transfers)} transfers successful"
                )
                logger.info(
                    f"Test 7.4: {validatedCount} transfers checksum-validated (≤5MB)"
                )
                logger.info(f"Test 7.4: Duration: {duration:.1f}s")
                logger.info(
                    f"Test 7.4: Overall throughput: {overallThroughput:.2f} MB/s (bidirectional)"
                )

                assert (
                    successCount >= 100
                ), f"Only {successCount}/{len(transfers)} transfers succeeded"

            finally:
                for conn in connections:
                    await conn.close()
        finally:
            await echoServer.close()

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_7_5_100_concurrent_transfers_server_to_client_tun1_client2(
        self,
    ):
        """Test 7.5: 100 Concurrent Transfers - Server-to-Client Tunnel 1 (Client 2)"""
        portConfig = get_port_config()

        numConnections = 100
        maxConcurrency = 20
        transferSizes = generateTransferSizes(
            numConnections, 100 * 1024, 250 * 1024 * 1024
        )

        totalDataSize = sum(transferSizes)
        logger.info(
            f"Test 7.5: {numConnections} connections, total data: {totalDataSize / (1024 * 1024):.1f}MB"
        )

        # Start echo server
        echoPort = portConfig.serverToClient2Tun1ConnectPort
        echoServer = UtilTcpSocket(
            "echo_backend_6_5",
            shouldEchoData=True,
            logTrafficEvents=False,
        )
        listening = await echoServer.startListen(port=echoPort, host="0.0.0.0")
        assert listening, f"Failed to start echo server on port {echoPort}"

        try:
            # Create all connections upfront
            tunnelPort = portConfig.serverToClientTun1ListenPort
            connections = []
            for i in range(numConnections):
                conn = UtilTcpSocket(
                    f"test_7_5_conn_{i}", logTrafficEvents=False
                )
                connected = await conn.startConnect("server", tunnelPort)
                if not connected:
                    logger.warning(
                        f"Test 7.5: Connection {i} failed to connect"
                    )
                    await conn.close()
                    continue
                connections.append(conn)

            logger.info(
                f"Test 7.5: {len(connections)}/{numConnections} connections established"
            )

            try:
                # Generate test data and create transfers
                transfers = []
                for i, (conn, size) in enumerate(
                    zip(connections, transferSizes)
                ):
                    testData = generateDeterministicData(size, seed=6005 + i)
                    transfer = UtilDataSendEnsureReceivedConnection(
                        f"transfer_{i}", testData, timeout=600.0
                    )
                    transfer.setConnection(conn)
                    transfers.append(transfer)

                # Run transfers with concurrency limit
                semaphore = asyncio.Semaphore(maxConcurrency)

                async def limitedTransfer(transfer):
                    async with semaphore:
                        return await transfer.executeTransfer()

                startTime = time.time()
                results = await asyncio.gather(
                    *[limitedTransfer(t) for t in transfers]
                )
                endTime = time.time()

                # Validate results
                successCount = 0
                validatedCount = 0
                totalThroughput = 0

                for i, (success, receivedData, throughput) in enumerate(
                    results
                ):
                    transfer = transfers[i]
                    size = transferSizes[i]

                    if not success:
                        logger.warning(
                            f"Test 7.5: Transfer {i} ({size / (1024 * 1024):.2f}MB) failed"
                        )
                        continue

                    if len(receivedData) != len(transfer.data):
                        logger.warning(
                            f"Test 7.5: Transfer {i} size mismatch: expected {len(transfer.data)}, got {len(receivedData)}"
                        )
                        continue

                    # Validate data content matches
                    if receivedData != transfer.data:
                        logger.warning(
                            f"Test 7.5: Transfer {i} data content mismatch"
                        )
                        continue

                    successCount += 1

                    # Only validate checksums for transfers 5MB or smaller
                    if size <= 5 * 1024 * 1024:
                        expectedChecksum = calculateSha256(transfer.data)
                        actualChecksum = calculateSha256(receivedData)
                        if actualChecksum != expectedChecksum:
                            logger.warning(
                                f"Test 7.5: Transfer {i} checksum mismatch"
                            )
                            continue
                        validatedCount += 1

                    totalThroughput += throughput

                duration = endTime - startTime
                overallThroughput = (
                    (totalDataSize * 2) / (1024 * 1024)
                ) / duration

                logger.info(
                    f"Test 7.5: {successCount}/{len(transfers)} transfers successful"
                )
                logger.info(
                    f"Test 7.5: {validatedCount} transfers checksum-validated (≤5MB)"
                )
                logger.info(f"Test 7.5: Duration: {duration:.1f}s")
                logger.info(
                    f"Test 7.5: Overall throughput: {overallThroughput:.2f} MB/s (bidirectional)"
                )

                assert (
                    successCount >= 100
                ), f"Only {successCount}/{len(transfers)} transfers succeeded"

            finally:
                for conn in connections:
                    await conn.close()
        finally:
            await echoServer.close()

    @pytest.mark.asyncio
    async def test_7_6_back_to_client_1_failover(self):
        """Test 7.6: Back to Client 1 Failover"""
        await triggerFailoverBackToClient1()
