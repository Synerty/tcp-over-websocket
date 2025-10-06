import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
import logging

import pytest

from util_socket_methods import (
    resetActiveClient,
    triggerFailoverToClient2,
    triggerFailoverBackToClient1,
)
from util_port_config import get_port_config
from util_tcp_socket import ConnectionEndState, UtilTcpSocket

logger = logging.getLogger(__name__)


def generate_unique_data(connection_id: int, size: int = 1024) -> bytes:
    """Generate unique test data for a connection"""
    data = bytearray(size)
    for i in range(size):
        data[i] = (connection_id * 100 + i) % 256
    return bytes(data)


class TestConcurrentConnections:
    """Test Suite 4: Multiple Concurrent Connections"""

    @pytest.mark.asyncio
    async def test_0_0_reset_active_client(self):
        """Test 0.0: Reset Active Client"""
        await resetActiveClient()

    @pytest.mark.asyncio
    async def test_5_1_10_concurrent_connections_client1(self):
        """Test 5.1: 10 Concurrent Connections - Client 1"""
        portConfig = get_port_config()

        # Track connected clients
        connected_clients = []

        async def on_client_connected(clientId: int):
            connected_clients.append(clientId)
            logger.debug(f"Echo server 4.1: client {clientId} connected")

        # Start echo server on shared backend port
        echo_port = portConfig.clientToServerTun1ConnectPort
        echo_server = UtilTcpSocket("echo_backend_4_1", shouldEchoData=True)
        echo_server.setOnClientConnected(on_client_connected)
        listening = await echo_server.startListen(port=echo_port, host="0.0.0.0")
        assert listening, f"Failed to start echo server on port {echo_port}"

        try:
            tunnel_port = portConfig.client1ToServerTun1ListenPort
            connections = []
            success_count = 0

            # Create and connect 10 connections
            for i in range(10):
                conn = UtilTcpSocket(f"test_5_1_conn_{i}")
                connected = await conn.startConnect("client1", tunnel_port)
                if connected:
                    connections.append((conn, i))
                else:
                    logger.warning(f"Test 5.1: Connection {i} failed to connect")
                    await conn.close()

            logger.info(
                f"Test 5.1: Successfully connected {len(connections)}/10 connections"
            )

            try:
                # Send unique data on each connection concurrently
                async def test_connection(conn_and_id):
                    conn, conn_id = conn_and_id
                    try:
                        test_data = generate_unique_data(conn_id, 1024)
                        received_data, success = await conn.sendDataExpectEcho(
                            test_data, timeout=60.0
                        )

                        if (
                            success
                            and len(received_data) == len(test_data)
                            and received_data == test_data
                        ):
                            logger.debug(f"Test 5.1: Connection {conn_id} successful")
                            return True
                        else:
                            if not success:
                                logger.warning(
                                    f"Test 5.1: Connection {conn_id} failed to send/receive"
                                )
                            elif len(received_data) != len(test_data):
                                logger.warning(
                                    f"Test 5.1: Connection {conn_id} length mismatch: sent {len(test_data)}, received {len(received_data)}"
                                )
                            else:
                                logger.warning(
                                    f"Test 5.1: Connection {conn_id} data mismatch: received data differs from sent data"
                                )
                            return False
                    except Exception as e:
                        logger.warning(f"Test 5.1: Connection {conn_id} exception: {e}")
                        return False

                # Test all connections concurrently
                results = await asyncio.gather(
                    *[test_connection(conn_info) for conn_info in connections]
                )
                success_count = sum(results)

                logger.info(
                    f"Test 5.1: {success_count}/{len(connections)} connections successful"
                )

                assert (
                    success_count >= 9
                ), f"Success count {success_count} below required minimum 9"
                logger.info(
                    "Test 5.1: Successfully validated 10 concurrent connections (client 1)"
                )
            finally:
                # Close all connections
                for conn, _ in connections:
                    await conn.close()
        finally:
            await echo_server.close()

    @pytest.mark.asyncio
    async def test_5_2_10_concurrent_connections_server_to_client(self):
        """Test 5.2: 10 Concurrent Connections - Server-to-Client"""
        portConfig = get_port_config()

        # Track connected clients
        connected_clients = []

        async def on_client_connected(clientId: int):
            connected_clients.append(clientId)
            logger.debug(f"Echo server 4.2: client {clientId} connected")

        # Start echo server on backend port
        echo_port = portConfig.serverToClient1Tun1ConnectPort
        echo_server = UtilTcpSocket("echo_backend_4_2", shouldEchoData=True)
        echo_server.setOnClientConnected(on_client_connected)
        listening = await echo_server.startListen(port=echo_port, host="0.0.0.0")
        assert listening, f"Failed to start echo server on port {echo_port}"

        try:
            tunnel_port = portConfig.serverToClientTun1ListenPort
            connections = []
            success_count = 0

            # Create and connect 10 connections
            for i in range(10):
                conn = UtilTcpSocket(f"test_5_2_conn_{i}")
                connected = await conn.startConnect("server", tunnel_port)
                if connected:
                    connections.append((conn, i))
                else:
                    logger.warning(f"Test 5.2: Connection {i} failed to connect")
                    await conn.close()

            logger.info(
                f"Test 5.2: Successfully connected {len(connections)}/10 connections"
            )

            try:
                # Send unique data on each connection concurrently
                async def test_connection(conn_and_id):
                    conn, conn_id = conn_and_id
                    try:
                        test_data = generate_unique_data(conn_id, 1024)
                        received_data, success = await conn.sendDataExpectEcho(
                            test_data, timeout=60.0
                        )

                        if (
                            success
                            and len(received_data) == len(test_data)
                            and received_data == test_data
                        ):
                            logger.debug(f"Test 5.2: Connection {conn_id} successful")
                            return True
                        else:
                            if not success:
                                logger.warning(
                                    f"Test 5.2: Connection {conn_id} failed to send/receive"
                                )
                            elif len(received_data) != len(test_data):
                                logger.warning(
                                    f"Test 5.2: Connection {conn_id} length mismatch: sent {len(test_data)}, received {len(received_data)}"
                                )
                            else:
                                logger.warning(
                                    f"Test 5.2: Connection {conn_id} data mismatch: received data differs from sent data"
                                )
                            return False
                    except Exception as e:
                        logger.warning(f"Test 5.2: Connection {conn_id} exception: {e}")
                        return False

                # Test all connections concurrently
                results = await asyncio.gather(
                    *[test_connection(conn_info) for conn_info in connections]
                )
                success_count = sum(results)

                logger.info(
                    f"Test 5.2: {success_count}/{len(connections)} connections successful"
                )

                assert (
                    success_count >= 9
                ), f"Success count {success_count} below required minimum 9"
                logger.info(
                    "Test 5.2: Successfully validated 10 concurrent connections (server-to-client)"
                )
            finally:
                # Close all connections
                for conn, _ in connections:
                    await conn.close()
        finally:
            await echo_server.close()

    @pytest.mark.asyncio
    async def test_5_3_20_sequential_connection_cycles_client1(self):
        """Test 5.3: 20 Sequential Connection Cycles - Client 1"""
        portConfig = get_port_config()

        # Start echo server on shared backend port
        echo_port = portConfig.clientToServerTun1ConnectPort
        echo_server = UtilTcpSocket("echo_backend_4_3", shouldEchoData=True)
        listening = await echo_server.startListen(port=echo_port, host="0.0.0.0")
        assert listening, f"Failed to start echo server on port {echo_port}"

        try:
            tunnel_port = portConfig.client1ToServerTun1ListenPort
            success_count = 0

            for i in range(20):
                conn = UtilTcpSocket(f"test_5_3_cycle_{i}")
                try:
                    # Connect
                    connected = await conn.startConnect("client1", tunnel_port)
                    if not connected:
                        logger.warning(f"Test 5.3: Cycle {i+1} failed to connect")
                        continue

                    # Send data
                    test_data = generate_unique_data(i, 512)
                    received_data, success = await conn.sendDataExpectEcho(
                        test_data, timeout=30.0
                    )

                    # Validate
                    if success and len(received_data) == len(test_data):
                        success_count += 1
                        logger.debug(f"Test 5.3: Cycle {i+1} successful")
                    else:
                        logger.warning(f"Test 5.3: Cycle {i+1} failed validation")

                except Exception as e:
                    logger.warning(f"Test 5.3: Cycle {i+1} exception: {e}")
                finally:
                    # Always close connection
                    await conn.close()

            logger.info(f"Test 5.3: {success_count}/20 cycles successful")

            assert (
                success_count >= 18
            ), f"Success count {success_count} below required minimum 18"
            logger.info(
                "Test 5.3: Successfully validated 20 sequential connection cycles (client 1)"
            )
        finally:
            await echo_server.close()

    @pytest.mark.asyncio
    async def test_5_4_failover_event(self):
        """Test 5.4: Failover Event"""
        await triggerFailoverToClient2()

    @pytest.mark.asyncio
    async def test_5_5_10_concurrent_connections_client2(self):
        """Test 5.5: 10 Concurrent Connections - Client 2"""
        portConfig = get_port_config()

        # Track connected clients
        connected_clients = []

        async def on_client_connected(clientId: int):
            connected_clients.append(clientId)
            logger.debug(f"Echo server 4.5: client {clientId} connected")

        # Start echo server on shared backend port
        echo_port = portConfig.clientToServerTun1ConnectPort
        echo_server = UtilTcpSocket("echo_backend_4_5", shouldEchoData=True)
        echo_server.setOnClientConnected(on_client_connected)
        listening = await echo_server.startListen(port=echo_port, host="0.0.0.0")
        assert listening, f"Failed to start echo server on port {echo_port}"

        try:
            tunnel_port = portConfig.client2ToServerTun1ListenPort
            connections = []
            success_count = 0

            # Create and connect 10 connections
            for i in range(10):
                conn = UtilTcpSocket(f"test_5_5_conn_{i}")
                connected = await conn.startConnect("client2", tunnel_port)
                if connected:
                    connections.append((conn, i))
                else:
                    logger.warning(f"Test 5.5: Connection {i} failed to connect")
                    await conn.close()

            logger.info(
                f"Test 5.5: Successfully connected {len(connections)}/10 connections"
            )

            try:
                # Send unique data on each connection concurrently
                async def test_connection(conn_and_id):
                    conn, conn_id = conn_and_id
                    try:
                        test_data = generate_unique_data(conn_id, 1024)
                        received_data, success = await conn.sendDataExpectEcho(
                            test_data, timeout=60.0
                        )

                        if (
                            success
                            and len(received_data) == len(test_data)
                            and received_data == test_data
                        ):
                            logger.debug(f"Test 5.5: Connection {conn_id} successful")
                            return True
                        else:
                            if not success:
                                logger.warning(
                                    f"Test 5.5: Connection {conn_id} failed to send/receive"
                                )
                            elif len(received_data) != len(test_data):
                                logger.warning(
                                    f"Test 5.5: Connection {conn_id} length mismatch: sent {len(test_data)}, received {len(received_data)}"
                                )
                            else:
                                logger.warning(
                                    f"Test 5.5: Connection {conn_id} data mismatch: received data differs from sent data"
                                )
                            return False
                    except Exception as e:
                        logger.warning(f"Test 5.5: Connection {conn_id} exception: {e}")
                        return False

                # Test all connections concurrently
                results = await asyncio.gather(
                    *[test_connection(conn_info) for conn_info in connections]
                )
                success_count = sum(results)

                logger.info(
                    f"Test 5.5: {success_count}/{len(connections)} connections successful"
                )

                assert (
                    success_count >= 9
                ), f"Success count {success_count} below required minimum 9"
                logger.info(
                    "Test 5.5: Successfully validated 10 concurrent connections (client 2)"
                )
            finally:
                # Close all connections
                for conn, _ in connections:
                    await conn.close()
        finally:
            await echo_server.close()

    @pytest.mark.asyncio
    async def test_5_6_10_concurrent_connections_server_to_client_client2(self):
        """Test 5.6: 10 Concurrent Connections - Server-to-Client (Client 2)"""
        portConfig = get_port_config()

        # Track connected clients
        connected_clients = []

        async def on_client_connected(clientId: int):
            connected_clients.append(clientId)
            logger.debug(f"Echo server 4.6: client {clientId} connected")

        # Start echo server on client2 backend port
        echo_port = portConfig.serverToClient2Tun1ConnectPort
        echo_server = UtilTcpSocket("echo_backend_4_6", shouldEchoData=True)
        echo_server.setOnClientConnected(on_client_connected)
        listening = await echo_server.startListen(port=echo_port, host="0.0.0.0")
        assert listening, f"Failed to start echo server on port {echo_port}"

        try:
            connections = []
            tunnel_port = portConfig.serverToClientTun1ListenPort
            success_count = 0

            # Create and connect 10 connections
            for i in range(10):
                conn = UtilTcpSocket(f"test_5_6_conn_{i}")
                connected = await conn.startConnect("server", tunnel_port)
                if connected:
                    connections.append((conn, i))
                else:
                    logger.warning(f"Test 5.6: Connection {i} failed to connect")
                    await conn.close()

            logger.info(
                f"Test 5.6: Successfully connected {len(connections)}/10 connections"
            )

            try:
                # Send unique data on each connection concurrently
                async def test_connection(conn_and_id):
                    conn, conn_id = conn_and_id
                    try:
                        test_data = generate_unique_data(conn_id, 1024)
                        received_data, success = await conn.sendDataExpectEcho(
                            test_data, timeout=60.0
                        )

                        if (
                            success
                            and len(received_data) == len(test_data)
                            and received_data == test_data
                        ):
                            logger.debug(f"Test 5.6: Connection {conn_id} successful")
                            return True
                        else:
                            if not success:
                                logger.warning(
                                    f"Test 5.6: Connection {conn_id} failed to send/receive"
                                )
                            elif len(received_data) != len(test_data):
                                logger.warning(
                                    f"Test 5.6: Connection {conn_id} length mismatch: sent {len(test_data)}, received {len(received_data)}"
                                )
                            else:
                                logger.warning(
                                    f"Test 5.6: Connection {conn_id} data mismatch: received data differs from sent data"
                                )
                            return False
                    except Exception as e:
                        logger.warning(f"Test 5.6: Connection {conn_id} exception: {e}")
                        return False

                # Test all connections concurrently
                results = await asyncio.gather(
                    *[test_connection(conn_info) for conn_info in connections]
                )
                success_count = sum(results)

                logger.info(
                    f"Test 5.6: {success_count}/{len(connections)} connections successful"
                )

                assert (
                    success_count >= 9
                ), f"Success count {success_count} below required minimum 9"
                logger.info(
                    "Test 5.6: Successfully validated 10 concurrent connections (server-to-client, client 2)"
                )
            finally:
                # Close all connections
                for conn, _ in connections:
                    await conn.close()
        finally:
            await echo_server.close()

    @pytest.mark.asyncio
    async def test_5_7_20_sequential_connection_cycles_client2(self):
        """Test 5.7: 20 Sequential Connection Cycles - Client 2"""
        portConfig = get_port_config()

        # Start echo server on shared backend port
        echo_port = portConfig.clientToServerTun1ConnectPort
        echo_server = UtilTcpSocket("echo_backend_4_7", shouldEchoData=True)
        listening = await echo_server.startListen(port=echo_port, host="0.0.0.0")
        assert listening, f"Failed to start echo server on port {echo_port}"

        try:
            tunnel_port = portConfig.client2ToServerTun1ListenPort
            success_count = 0

            for i in range(20):
                conn = UtilTcpSocket(f"test_5_7_cycle_{i}")
                try:
                    # Connect
                    connected = await conn.startConnect("client2", tunnel_port)
                    if not connected:
                        logger.warning(f"Test 5.7: Cycle {i+1} failed to connect")
                        continue

                    # Send data
                    test_data = generate_unique_data(i, 512)
                    received_data, success = await conn.sendDataExpectEcho(
                        test_data, timeout=30.0
                    )

                    # Validate
                    if success and len(received_data) == len(test_data):
                        success_count += 1
                        logger.debug(f"Test 5.7: Cycle {i+1} successful")
                    else:
                        logger.warning(f"Test 5.7: Cycle {i+1} failed validation")

                except Exception as e:
                    logger.warning(f"Test 5.7: Cycle {i+1} exception: {e}")
                finally:
                    # Always close connection
                    await conn.close()

            logger.info(f"Test 5.7: {success_count}/20 cycles successful")

            assert (
                success_count >= 18
            ), f"Success count {success_count} below required minimum 18"
            logger.info(
                "Test 5.7: Successfully validated 20 sequential connection cycles (client 2)"
            )
        finally:
            await echo_server.close()

    @pytest.mark.asyncio
    async def test_5_8_back_to_client_1_failover(self):
        """Test 5.8: Back to Client 1 Failover"""
        await triggerFailoverBackToClient1()