import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging

import pytest

from util_data_methods import calculateSha256
from util_data_methods import generateDeterministicData
from util_port_config import get_port_config
from util_socket_methods import resetActiveClient
from util_socket_methods import triggerFailoverBackToClient1
from util_socket_methods import triggerFailoverToClient2
from util_tcp_socket import UtilTcpSocket

logger = logging.getLogger(__name__)


class TestDataQuality:
    """Test Suite 2: Data Quality Tests - Client 1 and Client 2"""

    @pytest.mark.asyncio
    async def test_0_0_reset_active_client(self):
        """Test 0.0: Reset Active Client"""
        await resetActiveClient()

    @pytest.mark.asyncio
    async def test_3_1_100mb_server_to_client_tun1(self):
        """Test 3.1: 100MB Server-to-Client Tunnel 1"""
        portConfig = get_port_config()

        # Generate 100MB deterministic data
        data_size = 100 * 1024 * 1024  # 100MB
        test_data = generateDeterministicData(data_size, seed=2001)
        expected_checksum = calculateSha256(test_data)
        logger.info(
            f"Test 3.1: Generated {data_size} bytes, checksum: {expected_checksum}"
        )

        # Start echo server on backend port
        echo_port = portConfig.serverToClient1Tun1ConnectPort
        echo_server = UtilTcpSocket("echo_backend_2_1", shouldEchoData=True)
        listening = await echo_server.startListen(
            port=echo_port, host="0.0.0.0"
        )
        assert listening, f"Failed to start echo server on port {echo_port}"

        try:
            # Connect to tunnel endpoint
            tunnel_port = portConfig.serverToClientTun1ListenPort
            conn = UtilTcpSocket("test_3_1")
            connected = await conn.startConnect("server", tunnel_port)
            assert connected, f"Failed to connect to server:{tunnel_port}"

            try:
                # Send data and receive echo
                received_data, success = await conn.sendDataExpectEcho(
                    test_data, timeout=300.0
                )

                assert success, "Failed to send and receive 100MB data"
                assert (
                    len(received_data) == data_size
                ), f"Received data size mismatch: expected {data_size}, got {len(received_data)}"

                # Verify checksum
                actual_checksum = calculateSha256(received_data)
                assert (
                    actual_checksum == expected_checksum
                ), f"Checksum mismatch: expected {expected_checksum}, got {actual_checksum}"

                logger.info(
                    "Test 3.1: Successfully validated 100MB server-to-client tunnel 1"
                )
            finally:
                await conn.close()
        finally:
            await echo_server.close()

    @pytest.mark.asyncio
    async def test_3_2_100mb_server_to_client_tun2(self):
        """Test 3.2: 100MB Server-to-Client Tunnel 2"""
        portConfig = get_port_config()

        # Generate 100MB deterministic data
        data_size = 100 * 1024 * 1024  # 100MB
        test_data = generateDeterministicData(data_size, seed=2002)
        expected_checksum = calculateSha256(test_data)
        logger.info(
            f"Test 3.2: Generated {data_size} bytes, checksum: {expected_checksum}"
        )

        # Start echo server on backend port
        echo_port = portConfig.serverToClient1Tun2ConnectPort
        echo_server = UtilTcpSocket("echo_backend_2_2", shouldEchoData=True)
        listening = await echo_server.startListen(
            port=echo_port, host="0.0.0.0"
        )
        assert listening, f"Failed to start echo server on port {echo_port}"

        try:
            # Connect to tunnel endpoint
            tunnel_port = portConfig.serverToClientTun2ListenPort
            conn = UtilTcpSocket("test_3_2")
            connected = await conn.startConnect("server", tunnel_port)
            assert connected, f"Failed to connect to server:{tunnel_port}"

            try:
                # Send data and receive echo
                received_data, success = await conn.sendDataExpectEcho(
                    test_data, timeout=300.0
                )

                assert success, "Failed to send and receive 100MB data"
                assert (
                    len(received_data) == data_size
                ), f"Received data size mismatch: expected {data_size}, got {len(received_data)}"

                # Verify checksum
                actual_checksum = calculateSha256(received_data)
                assert (
                    actual_checksum == expected_checksum
                ), f"Checksum mismatch: expected {expected_checksum}, got {actual_checksum}"

                logger.info(
                    "Test 3.2: Successfully validated 100MB server-to-client tunnel 2"
                )
            finally:
                await conn.close()
        finally:
            await echo_server.close()

    @pytest.mark.asyncio
    async def test_3_3_100mb_client_to_server_tun1(self):
        """Test 3.3: 100MB Client-to-Server Tunnel 1"""
        portConfig = get_port_config()

        # Generate 100MB deterministic data
        data_size = 100 * 1024 * 1024  # 100MB
        test_data = generateDeterministicData(data_size, seed=2003)
        expected_checksum = calculateSha256(test_data)
        logger.info(
            f"Test 3.3: Generated {data_size} bytes, checksum: {expected_checksum}"
        )

        # Start echo server on shared backend port
        echo_port = portConfig.clientToServerTun1ConnectPort
        echo_server = UtilTcpSocket("echo_backend_2_3", shouldEchoData=True)
        listening = await echo_server.startListen(
            port=echo_port, host="0.0.0.0"
        )
        assert listening, f"Failed to start echo server on port {echo_port}"

        try:
            # Connect to client1 tunnel endpoint
            tunnel_port = portConfig.client1ToServerTun1ListenPort
            conn = UtilTcpSocket("test_3_3")
            connected = await conn.startConnect("client1", tunnel_port)
            assert connected, f"Failed to connect to client1:{tunnel_port}"

            try:
                # Send data and receive echo
                received_data, success = await conn.sendDataExpectEcho(
                    test_data, timeout=300.0
                )

                assert success, "Failed to send and receive 100MB data"
                assert (
                    len(received_data) == data_size
                ), f"Received data size mismatch: expected {data_size}, got {len(received_data)}"

                # Verify checksum
                actual_checksum = calculateSha256(received_data)
                assert (
                    actual_checksum == expected_checksum
                ), f"Checksum mismatch: expected {expected_checksum}, got {actual_checksum}"

                logger.info(
                    "Test 3.3: Successfully validated 100MB client-to-server tunnel 1"
                )
            finally:
                await conn.close()
        finally:
            await echo_server.close()

    @pytest.mark.asyncio
    async def test_3_4_100mb_client_to_server_tun2(self):
        """Test 3.4: 100MB Client-to-Server Tunnel 2"""
        portConfig = get_port_config()

        # Generate 100MB deterministic data
        data_size = 100 * 1024 * 1024  # 100MB
        test_data = generateDeterministicData(data_size, seed=2004)
        expected_checksum = calculateSha256(test_data)
        logger.info(
            f"Test 3.4: Generated {data_size} bytes, checksum: {expected_checksum}"
        )

        # Start echo server on shared backend port
        echo_port = portConfig.clientToServerTun2ConnectPort
        echo_server = UtilTcpSocket("echo_backend_2_4", shouldEchoData=True)
        listening = await echo_server.startListen(
            port=echo_port, host="0.0.0.0"
        )
        assert listening, f"Failed to start echo server on port {echo_port}"

        try:
            # Connect to client1 tunnel endpoint
            tunnel_port = portConfig.client1ToServerTun2ListenPort
            conn = UtilTcpSocket("test_3_4")
            connected = await conn.startConnect("client1", tunnel_port)
            assert connected, f"Failed to connect to client1:{tunnel_port}"

            try:
                # Send data and receive echo
                received_data, success = await conn.sendDataExpectEcho(
                    test_data, timeout=300.0
                )

                assert success, "Failed to send and receive 100MB data"
                assert (
                    len(received_data) == data_size
                ), f"Received data size mismatch: expected {data_size}, got {len(received_data)}"

                # Verify checksum
                actual_checksum = calculateSha256(received_data)
                assert (
                    actual_checksum == expected_checksum
                ), f"Checksum mismatch: expected {expected_checksum}, got {actual_checksum}"

                logger.info(
                    "Test 3.4: Successfully validated 100MB client-to-server tunnel 2"
                )
            finally:
                await conn.close()
        finally:
            await echo_server.close()

    @pytest.mark.asyncio
    async def test_3_5_failover_event(self):
        """Test 3.5: Failover Event"""
        await triggerFailoverToClient2()

    @pytest.mark.asyncio
    async def test_3_6_100mb_server_to_client_tun1_client2(self):
        """Test 3.6: 100MB Server-to-Client Tunnel 1 (Client 2)"""
        portConfig = get_port_config()

        # Generate 100MB deterministic data
        data_size = 100 * 1024 * 1024  # 100MB
        test_data = generateDeterministicData(data_size, seed=2006)
        expected_checksum = calculateSha256(test_data)
        logger.info(
            f"Test 3.6: Generated {data_size} bytes, checksum: {expected_checksum}"
        )

        # Start echo server on client2 backend port
        echo_port = portConfig.serverToClient2Tun1ConnectPort
        echo_server = UtilTcpSocket("echo_backend_2_6", shouldEchoData=True)
        listening = await echo_server.startListen(
            port=echo_port, host="0.0.0.0"
        )
        assert listening, f"Failed to start echo server on port {echo_port}"

        try:
            # Connect to tunnel endpoint
            tunnel_port = portConfig.serverToClientTun1ListenPort
            conn = UtilTcpSocket("test_3_6")
            connected = await conn.startConnect("server", tunnel_port)
            assert connected, f"Failed to connect to server:{tunnel_port}"

            try:
                # Send data and receive echo
                received_data, success = await conn.sendDataExpectEcho(
                    test_data, timeout=300.0
                )

                assert success, "Failed to send and receive 100MB data"
                assert (
                    len(received_data) == data_size
                ), f"Received data size mismatch: expected {data_size}, got {len(received_data)}"

                # Verify checksum
                actual_checksum = calculateSha256(received_data)
                assert (
                    actual_checksum == expected_checksum
                ), f"Checksum mismatch: expected {expected_checksum}, got {actual_checksum}"

                logger.info(
                    "Test 3.6: Successfully validated 100MB server-to-client tunnel 1 (client 2)"
                )
            finally:
                await conn.close()
        finally:
            await echo_server.close()

    @pytest.mark.asyncio
    async def test_3_7_100mb_server_to_client_tun2_client2(self):
        """Test 3.7: 100MB Server-to-Client Tunnel 2 (Client 2)"""
        portConfig = get_port_config()

        # Generate 100MB deterministic data
        data_size = 100 * 1024 * 1024  # 100MB
        test_data = generateDeterministicData(data_size, seed=2007)
        expected_checksum = calculateSha256(test_data)
        logger.info(
            f"Test 3.7: Generated {data_size} bytes, checksum: {expected_checksum}"
        )

        # Start echo server on client2 backend port
        echo_port = portConfig.serverToClient2Tun2ConnectPort
        echo_server = UtilTcpSocket("echo_backend_2_7", shouldEchoData=True)
        listening = await echo_server.startListen(
            port=echo_port, host="0.0.0.0"
        )
        assert listening, f"Failed to start echo server on port {echo_port}"

        try:
            # Connect to tunnel endpoint
            tunnel_port = portConfig.serverToClientTun2ListenPort
            conn = UtilTcpSocket("test_3_7")
            connected = await conn.startConnect("server", tunnel_port)
            assert connected, f"Failed to connect to server:{tunnel_port}"

            try:
                # Send data and receive echo
                received_data, success = await conn.sendDataExpectEcho(
                    test_data, timeout=300.0
                )

                assert success, "Failed to send and receive 100MB data"
                assert (
                    len(received_data) == data_size
                ), f"Received data size mismatch: expected {data_size}, got {len(received_data)}"

                # Verify checksum
                actual_checksum = calculateSha256(received_data)
                assert (
                    actual_checksum == expected_checksum
                ), f"Checksum mismatch: expected {expected_checksum}, got {actual_checksum}"

                logger.info(
                    "Test 3.7: Successfully validated 100MB server-to-client tunnel 2 (client 2)"
                )
            finally:
                await conn.close()
        finally:
            await echo_server.close()

    @pytest.mark.asyncio
    async def test_3_8_100mb_client_to_server_tun1_client2(self):
        """Test 3.8: 100MB Client-to-Server Tunnel 1 (Client 2)"""
        portConfig = get_port_config()

        # Generate 100MB deterministic data
        data_size = 100 * 1024 * 1024  # 100MB
        test_data = generateDeterministicData(data_size, seed=2008)
        expected_checksum = calculateSha256(test_data)
        logger.info(
            f"Test 3.8: Generated {data_size} bytes, checksum: {expected_checksum}"
        )

        # Start echo server on shared backend port
        echo_port = portConfig.clientToServerTun1ConnectPort
        echo_server = UtilTcpSocket("echo_backend_2_8", shouldEchoData=True)
        listening = await echo_server.startListen(
            port=echo_port, host="0.0.0.0"
        )
        assert listening, f"Failed to start echo server on port {echo_port}"

        try:
            # Connect to client2 tunnel endpoint
            tunnel_port = portConfig.client2ToServerTun1ListenPort
            conn = UtilTcpSocket("test_3_8")
            connected = await conn.startConnect("client2", tunnel_port)
            assert connected, f"Failed to connect to client2:{tunnel_port}"

            try:
                # Send data and receive echo
                received_data, success = await conn.sendDataExpectEcho(
                    test_data, timeout=300.0
                )

                assert success, "Failed to send and receive 100MB data"
                assert (
                    len(received_data) == data_size
                ), f"Received data size mismatch: expected {data_size}, got {len(received_data)}"

                # Verify checksum
                actual_checksum = calculateSha256(received_data)
                assert (
                    actual_checksum == expected_checksum
                ), f"Checksum mismatch: expected {expected_checksum}, got {actual_checksum}"

                logger.info(
                    "Test 3.8: Successfully validated 100MB client-to-server tunnel 1 (client 2)"
                )
            finally:
                await conn.close()
        finally:
            await echo_server.close()

    @pytest.mark.asyncio
    async def test_3_9_100mb_client_to_server_tun2_client2(self):
        """Test 3.9: 100MB Client-to-Server Tunnel 2 (Client 2)"""
        portConfig = get_port_config()

        # Generate 100MB deterministic data
        data_size = 100 * 1024 * 1024  # 100MB
        test_data = generateDeterministicData(data_size, seed=2009)
        expected_checksum = calculateSha256(test_data)
        logger.info(
            f"Test 3.9: Generated {data_size} bytes, checksum: {expected_checksum}"
        )

        # Start echo server on shared backend port
        echo_port = portConfig.clientToServerTun2ConnectPort
        echo_server = UtilTcpSocket("echo_backend_2_9", shouldEchoData=True)
        listening = await echo_server.startListen(
            port=echo_port, host="0.0.0.0"
        )
        assert listening, f"Failed to start echo server on port {echo_port}"

        try:
            # Connect to client2 tunnel endpoint
            tunnel_port = portConfig.client2ToServerTun2ListenPort
            conn = UtilTcpSocket("test_3_9")
            connected = await conn.startConnect("client2", tunnel_port)
            assert connected, f"Failed to connect to client2:{tunnel_port}"

            try:
                # Send data and receive echo
                received_data, success = await conn.sendDataExpectEcho(
                    test_data, timeout=300.0
                )

                assert success, "Failed to send and receive 100MB data"
                assert (
                    len(received_data) == data_size
                ), f"Received data size mismatch: expected {data_size}, got {len(received_data)}"

                # Verify checksum
                actual_checksum = calculateSha256(received_data)
                assert (
                    actual_checksum == expected_checksum
                ), f"Checksum mismatch: expected {expected_checksum}, got {actual_checksum}"

                logger.info(
                    "Test 3.9: Successfully validated 100MB client-to-server tunnel 2 (client 2)"
                )
            finally:
                await conn.close()
        finally:
            await echo_server.close()

    @pytest.mark.asyncio
    async def test_3_10_back_to_client_1_failover(self):
        """Test 3.10: Back to Client 1 Failover"""
        await triggerFailoverBackToClient1()
