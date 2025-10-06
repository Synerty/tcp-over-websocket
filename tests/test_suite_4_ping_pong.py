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


def generate_test_packet(size: int, seed: int = 0) -> bytes:
    """Generate a test packet of specified size"""
    data = bytearray(size)
    for i in range(size):
        data[i] = (seed + i) % 256
    return bytes(data)


class TestPingPong:
    """Test Suite 3: Ping Pong Tests - 1000 iterations, 10ms delay, 500 byte packets"""

    @pytest.mark.asyncio
    async def test_0_0_reset_active_client(self):
        """Test 0.0: Reset Active Client"""
        await resetActiveClient()

    @pytest.mark.asyncio
    async def test_4_1_client_to_server_tun1_bidirectional(self):
        """Test 4.1: Client-to-Server Tunnel 1 Bidirectional"""
        portConfig = get_port_config()

        # Start echo server on shared backend port
        echo_port = portConfig.clientToServerTun1ConnectPort
        echo_server = UtilTcpSocket("echo_backend_3_1", shouldEchoData=True)
        listening = await echo_server.startListen(port=echo_port, host="0.0.0.0")
        assert listening, f"Failed to start echo server on port {echo_port}"

        try:
            # Connect to client1 tunnel endpoint
            tunnel_port = portConfig.client1ToServerTun1ListenPort
            conn = UtilTcpSocket("test_4_1")
            connected = await conn.startConnect("client1", tunnel_port)
            assert connected, f"Failed to connect to client1:{tunnel_port}"

            try:
                success_count = 0
                test_packet = generate_test_packet(500, seed=3001)

                logger.info("Test 4.1: Starting 1000 ping-pong iterations")

                for i in range(1000):
                    try:
                        # Send 500 bytes and wait for echo
                        if await conn.write(test_packet):
                            received_data = await conn.read(500, timeout=10.0)
                            if received_data and len(received_data) == 500:
                                success_count += 1
                            else:
                                logger.warning(
                                    f"Test 4.1: Iteration {i+1} - received incomplete data"
                                )
                        else:
                            logger.warning(f"Test 4.1: Iteration {i+1} - write failed")

                        # Wait 10ms between iterations
                        await asyncio.sleep(0.01)
                    except Exception as e:
                        logger.warning(f"Test 4.1: Iteration {i+1} failed: {e}")

                success_rate = (success_count / 1000) * 100
                logger.info(
                    f"Test 4.1: Success rate: {success_rate}% ({success_count}/1000)"
                )

                assert (
                    success_rate >= 95
                ), f"Success rate {success_rate}% below required 95%"
                logger.info(
                    "Test 4.1: Successfully validated client-to-server tunnel 1 bidirectional"
                )
            finally:
                await conn.close()
        finally:
            await echo_server.close()

    @pytest.mark.asyncio
    async def test_4_2_client_to_server_tun2_bidirectional(self):
        """Test 4.2: Client-to-Server Tunnel 2 Bidirectional"""
        portConfig = get_port_config()

        # Start echo server on shared backend port
        echo_port = portConfig.clientToServerTun2ConnectPort
        echo_server = UtilTcpSocket("echo_backend_3_2", shouldEchoData=True)
        listening = await echo_server.startListen(port=echo_port, host="0.0.0.0")
        assert listening, f"Failed to start echo server on port {echo_port}"

        try:
            # Connect to client1 tunnel endpoint
            tunnel_port = portConfig.client1ToServerTun2ListenPort
            conn = UtilTcpSocket("test_4_2")
            connected = await conn.startConnect("client1", tunnel_port)
            assert connected, f"Failed to connect to client1:{tunnel_port}"

            try:
                success_count = 0
                test_packet = generate_test_packet(500, seed=3002)

                logger.info("Test 4.2: Starting 1000 ping-pong iterations")

                for i in range(1000):
                    try:
                        # Send 500 bytes and wait for echo
                        if await conn.write(test_packet):
                            received_data = await conn.read(500, timeout=10.0)
                            if received_data and len(received_data) == 500:
                                success_count += 1
                            else:
                                logger.warning(
                                    f"Test 4.2: Iteration {i+1} - received incomplete data"
                                )
                        else:
                            logger.warning(f"Test 4.2: Iteration {i+1} - write failed")

                        # Wait 10ms between iterations
                        await asyncio.sleep(0.01)
                    except Exception as e:
                        logger.warning(f"Test 4.2: Iteration {i+1} failed: {e}")

                success_rate = (success_count / 1000) * 100
                logger.info(
                    f"Test 4.2: Success rate: {success_rate}% ({success_count}/1000)"
                )

                assert (
                    success_rate >= 95
                ), f"Success rate {success_rate}% below required 95%"
                logger.info(
                    "Test 4.2: Successfully validated client-to-server tunnel 2 bidirectional"
                )
            finally:
                await conn.close()
        finally:
            await echo_server.close()

    @pytest.mark.asyncio
    async def test_4_3_server_to_client_tun1_bidirectional(self):
        """Test 4.3: Server-to-Client Tunnel 1 Bidirectional"""
        portConfig = get_port_config()

        # Start echo server on backend port
        echo_port = portConfig.serverToClient1Tun1ConnectPort
        echo_server = UtilTcpSocket("echo_backend_3_3", shouldEchoData=True)
        listening = await echo_server.startListen(port=echo_port, host="0.0.0.0")
        assert listening, f"Failed to start echo server on port {echo_port}"

        try:
            # Connect to server tunnel endpoint
            tunnel_port = portConfig.serverToClientTun1ListenPort
            conn = UtilTcpSocket("test_4_3")
            connected = await conn.startConnect("server", tunnel_port)
            assert connected, f"Failed to connect to server:{tunnel_port}"

            try:
                success_count = 0
                test_packet = generate_test_packet(500, seed=3003)

                logger.info("Test 4.3: Starting 1000 ping-pong iterations")

                for i in range(1000):
                    try:
                        # Send 500 bytes and wait for echo
                        if await conn.write(test_packet):
                            received_data = await conn.read(500, timeout=10.0)
                            if received_data and len(received_data) == 500:
                                success_count += 1
                            else:
                                logger.warning(
                                    f"Test 4.3: Iteration {i+1} - received incomplete data"
                                )
                        else:
                            logger.warning(f"Test 4.3: Iteration {i+1} - write failed")

                        # Wait 10ms between iterations
                        await asyncio.sleep(0.01)
                    except Exception as e:
                        logger.warning(f"Test 4.3: Iteration {i+1} failed: {e}")

                success_rate = (success_count / 1000) * 100
                logger.info(
                    f"Test 4.3: Success rate: {success_rate}% ({success_count}/1000)"
                )

                assert (
                    success_rate >= 95
                ), f"Success rate {success_rate}% below required 95%"
                logger.info(
                    "Test 4.3: Successfully validated server-to-client tunnel 1 bidirectional"
                )
            finally:
                await conn.close()
        finally:
            await echo_server.close()

    @pytest.mark.asyncio
    async def test_4_4_server_to_client_tun2_bidirectional(self):
        """Test 4.4: Server-to-Client Tunnel 2 Bidirectional"""
        portConfig = get_port_config()

        # Start echo server on backend port
        echo_port = portConfig.serverToClient1Tun2ConnectPort
        echo_server = UtilTcpSocket("echo_backend_3_4", shouldEchoData=True)
        listening = await echo_server.startListen(port=echo_port, host="0.0.0.0")
        assert listening, f"Failed to start echo server on port {echo_port}"

        try:
            # Connect to server tunnel endpoint
            tunnel_port = portConfig.serverToClientTun2ListenPort
            conn = UtilTcpSocket("test_4_4")
            connected = await conn.startConnect("server", tunnel_port)
            assert connected, f"Failed to connect to server:{tunnel_port}"

            try:
                success_count = 0
                test_packet = generate_test_packet(500, seed=3004)

                logger.info("Test 4.4: Starting 1000 ping-pong iterations")

                for i in range(1000):
                    try:
                        # Send 500 bytes and wait for echo
                        if await conn.write(test_packet):
                            received_data = await conn.read(500, timeout=10.0)
                            if received_data and len(received_data) == 500:
                                success_count += 1
                            else:
                                logger.warning(
                                    f"Test 4.4: Iteration {i+1} - received incomplete data"
                                )
                        else:
                            logger.warning(f"Test 4.4: Iteration {i+1} - write failed")

                        # Wait 10ms between iterations
                        await asyncio.sleep(0.01)
                    except Exception as e:
                        logger.warning(f"Test 4.4: Iteration {i+1} failed: {e}")

                success_rate = (success_count / 1000) * 100
                logger.info(
                    f"Test 4.4: Success rate: {success_rate}% ({success_count}/1000)"
                )

                assert (
                    success_rate >= 95
                ), f"Success rate {success_rate}% below required 95%"
                logger.info(
                    "Test 4.4: Successfully validated server-to-client tunnel 2 bidirectional"
                )
            finally:
                await conn.close()
        finally:
            await echo_server.close()

    @pytest.mark.asyncio
    async def test_4_5_failover_event(self):
        """Test 4.5: Failover Event"""
        await triggerFailoverToClient2()

    @pytest.mark.asyncio
    async def test_4_6_client_to_server_tun1_bidirectional_client2(self):
        """Test 4.6: Client-to-Server Tunnel 1 Bidirectional (Client 2)"""
        portConfig = get_port_config()

        # Start echo server on shared backend port
        echo_port = portConfig.clientToServerTun1ConnectPort
        echo_server = UtilTcpSocket("echo_backend_3_6", shouldEchoData=True)
        listening = await echo_server.startListen(port=echo_port, host="0.0.0.0")
        assert listening, f"Failed to start echo server on port {echo_port}"

        try:
            # Connect to client2 tunnel endpoint
            tunnel_port = portConfig.client2ToServerTun1ListenPort
            conn = UtilTcpSocket("test_4_6")
            connected = await conn.startConnect("client2", tunnel_port)
            assert connected, f"Failed to connect to client2:{tunnel_port}"

            try:
                success_count = 0
                test_packet = generate_test_packet(500, seed=3006)

                logger.info("Test 4.6: Starting 1000 ping-pong iterations (client 2)")

                for i in range(1000):
                    try:
                        # Send 500 bytes and wait for echo
                        if await conn.write(test_packet):
                            received_data = await conn.read(500, timeout=10.0)
                            if received_data and len(received_data) == 500:
                                success_count += 1
                            else:
                                logger.warning(
                                    f"Test 4.6: Iteration {i+1} - received incomplete data"
                                )
                        else:
                            logger.warning(f"Test 4.6: Iteration {i+1} - write failed")

                        # Wait 10ms between iterations
                        await asyncio.sleep(0.01)
                    except Exception as e:
                        logger.warning(f"Test 4.6: Iteration {i+1} failed: {e}")

                success_rate = (success_count / 1000) * 100
                logger.info(
                    f"Test 4.6: Success rate: {success_rate}% ({success_count}/1000)"
                )

                assert (
                    success_rate >= 95
                ), f"Success rate {success_rate}% below required 95%"
                logger.info(
                    "Test 4.6: Successfully validated client-to-server tunnel 1 bidirectional (client 2)"
                )
            finally:
                await conn.close()
        finally:
            await echo_server.close()

    @pytest.mark.asyncio
    async def test_4_7_client_to_server_tun2_bidirectional_client2(self):
        """Test 4.7: Client-to-Server Tunnel 2 Bidirectional (Client 2)"""
        portConfig = get_port_config()

        # Start echo server on shared backend port
        echo_port = portConfig.clientToServerTun2ConnectPort
        echo_server = UtilTcpSocket("echo_backend_3_7", shouldEchoData=True)
        listening = await echo_server.startListen(port=echo_port, host="0.0.0.0")
        assert listening, f"Failed to start echo server on port {echo_port}"

        try:
            # Connect to client2 tunnel endpoint
            tunnel_port = portConfig.client2ToServerTun2ListenPort
            conn = UtilTcpSocket("test_4_7")
            connected = await conn.startConnect("client2", tunnel_port)
            assert connected, f"Failed to connect to client2:{tunnel_port}"

            try:
                success_count = 0
                test_packet = generate_test_packet(500, seed=3007)

                logger.info("Test 4.7: Starting 1000 ping-pong iterations (client 2)")

                for i in range(1000):
                    try:
                        # Send 500 bytes and wait for echo
                        if await conn.write(test_packet):
                            received_data = await conn.read(500, timeout=10.0)
                            if received_data and len(received_data) == 500:
                                success_count += 1
                            else:
                                logger.warning(
                                    f"Test 4.7: Iteration {i+1} - received incomplete data"
                                )
                        else:
                            logger.warning(f"Test 4.7: Iteration {i+1} - write failed")

                        # Wait 10ms between iterations
                        await asyncio.sleep(0.01)
                    except Exception as e:
                        logger.warning(f"Test 4.7: Iteration {i+1} failed: {e}")

                success_rate = (success_count / 1000) * 100
                logger.info(
                    f"Test 4.7: Success rate: {success_rate}% ({success_count}/1000)"
                )

                assert (
                    success_rate >= 95
                ), f"Success rate {success_rate}% below required 95%"
                logger.info(
                    "Test 4.7: Successfully validated client-to-server tunnel 2 bidirectional (client 2)"
                )
            finally:
                await conn.close()
        finally:
            await echo_server.close()

    @pytest.mark.asyncio
    async def test_4_8_server_to_client_tun1_bidirectional_client2(self):
        """Test 4.8: Server-to-Client Tunnel 1 Bidirectional (Client 2)"""
        portConfig = get_port_config()

        # Start echo server on client2 backend port
        echo_port = portConfig.serverToClient2Tun1ConnectPort
        echo_server = UtilTcpSocket("echo_backend_3_8", shouldEchoData=True)
        listening = await echo_server.startListen(port=echo_port, host="0.0.0.0")
        assert listening, f"Failed to start echo server on port {echo_port}"

        try:
            # Connect to server tunnel endpoint
            tunnel_port = portConfig.serverToClientTun1ListenPort
            conn = UtilTcpSocket("test_4_8")
            connected = await conn.startConnect("server", tunnel_port)
            assert connected, f"Failed to connect to server:{tunnel_port}"

            try:
                success_count = 0
                test_packet = generate_test_packet(500, seed=3008)

                logger.info("Test 4.8: Starting 1000 ping-pong iterations (client 2)")

                for i in range(1000):
                    try:
                        # Send 500 bytes and wait for echo
                        if await conn.write(test_packet):
                            received_data = await conn.read(500, timeout=10.0)
                            if received_data and len(received_data) == 500:
                                success_count += 1
                            else:
                                logger.warning(
                                    f"Test 4.8: Iteration {i+1} - received incomplete data"
                                )
                        else:
                            logger.warning(f"Test 4.8: Iteration {i+1} - write failed")

                        # Wait 10ms between iterations
                        await asyncio.sleep(0.01)
                    except Exception as e:
                        logger.warning(f"Test 4.8: Iteration {i+1} failed: {e}")

                success_rate = (success_count / 1000) * 100
                logger.info(
                    f"Test 4.8: Success rate: {success_rate}% ({success_count}/1000)"
                )

                assert (
                    success_rate >= 95
                ), f"Success rate {success_rate}% below required 95%"
                logger.info(
                    "Test 4.8: Successfully validated server-to-client tunnel 1 bidirectional (client 2)"
                )
            finally:
                await conn.close()
        finally:
            await echo_server.close()

    @pytest.mark.asyncio
    async def test_4_9_server_to_client_tun2_bidirectional_client2(self):
        """Test 4.9: Server-to-Client Tunnel 2 Bidirectional (Client 2)"""
        portConfig = get_port_config()

        # Start echo server on client2 backend port
        echo_port = portConfig.serverToClient2Tun2ConnectPort
        echo_server = UtilTcpSocket("echo_backend_3_9", shouldEchoData=True)
        listening = await echo_server.startListen(port=echo_port, host="0.0.0.0")
        assert listening, f"Failed to start echo server on port {echo_port}"

        try:
            # Connect to server tunnel endpoint
            tunnel_port = portConfig.serverToClientTun2ListenPort
            conn = UtilTcpSocket("test_4_9")
            connected = await conn.startConnect("server", tunnel_port)
            assert connected, f"Failed to connect to server:{tunnel_port}"

            try:
                success_count = 0
                test_packet = generate_test_packet(500, seed=3009)

                logger.info("Test 4.9: Starting 1000 ping-pong iterations (client 2)")

                for i in range(1000):
                    try:
                        # Send 500 bytes and wait for echo
                        if await conn.write(test_packet):
                            received_data = await conn.read(500, timeout=10.0)
                            if received_data and len(received_data) == 500:
                                success_count += 1
                            else:
                                logger.warning(
                                    f"Test 4.9: Iteration {i+1} - received incomplete data"
                                )
                        else:
                            logger.warning(f"Test 4.9: Iteration {i+1} - write failed")

                        # Wait 10ms between iterations
                        await asyncio.sleep(0.01)
                    except Exception as e:
                        logger.warning(f"Test 4.9: Iteration {i+1} failed: {e}")

                success_rate = (success_count / 1000) * 100
                logger.info(
                    f"Test 4.9: Success rate: {success_rate}% ({success_count}/1000)"
                )

                assert (
                    success_rate >= 95
                ), f"Success rate {success_rate}% below required 95%"
                logger.info(
                    "Test 4.9: Successfully validated server-to-client tunnel 2 bidirectional (client 2)"
                )
            finally:
                await conn.close()
        finally:
            await echo_server.close()

    @pytest.mark.asyncio
    async def test_4_10_back_to_client_1_failover(self):
        """Test 4.10: Back to Client 1 Failover"""
        await triggerFailoverBackToClient1()