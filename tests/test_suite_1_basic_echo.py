import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
import logging

import pytest

from util_socket_methods import resetActiveClient, triggerFailoverToClient2
from util_port_config import get_port_config
from util_tcp_socket import UtilTcpSocket

logger = logging.getLogger(__name__)


class TestBasicEcho:
    """Test Suite 1: Basic Echo Tests - Client 1 and Client 2"""

    @pytest.mark.asyncio
    async def test_0_0_reset_active_client(self):
        """Test 0.0: Reset Active Client"""
        await resetActiveClient()

    @pytest.mark.asyncio
    async def test_1_1_server_to_client_tun1_echo(self):
        """Test 1.1: Server-to-Client Tunnel 1 Echo"""
        portConfig = get_port_config()

        # Start echo server on backend port that tunnel will connect to
        echoPort = portConfig.serverToClient1Tun1ConnectPort
        echoServer = UtilTcpSocket(
            "echo_backend",
            shouldEchoData=True,
        )
        listening = await echoServer.startListen(port=echoPort, host="0.0.0.0")
        assert listening, f"Failed to start echo server on port {echoPort}"

        try:
            # Connect to tunnel endpoint
            tunnelPort = portConfig.serverToClientTun1ListenPort
            conn = UtilTcpSocket("test_1_1")
            connected = await conn.startConnect("server", tunnelPort)
            assert connected, f"Failed to connect to server:{tunnelPort}"

            try:
                # Send data through tunnel, receive echo from backend
                sentData = b"HELLO"
                receivedData, success = await conn.sendDataExpectEcho(sentData)

                assert success, "Failed to send and receive"
                assert (
                    b"HELLO" in receivedData
                ), "Response does not contain HELLO"
                logger.info(
                    "Test 1.1: Successfully validated server-to-client tunnel 1 echo"
                )
            finally:
                await conn.close()
        finally:
            await echoServer.close()

    @pytest.mark.asyncio
    async def test_1_2_client_to_server_tun1_echo(self):
        """Test 1.2: Client-to-Server Tunnel 1 Echo"""
        portConfig = get_port_config()

        # Start echo server on shared backend port
        echoPort = portConfig.clientToServerTun1ConnectPort
        echoServer = UtilTcpSocket(
            "echo_backend",
            shouldEchoData=True,
        )
        listening = await echoServer.startListen(port=echoPort, host="0.0.0.0")
        assert listening, f"Failed to start echo server on port {echoPort}"

        try:
            # Connect to client1 tunnel endpoint
            tunnelPort = portConfig.client1ToServerTun1ListenPort
            conn = UtilTcpSocket("test_1_2")
            connected = await conn.startConnect("client1", tunnelPort)
            assert connected, f"Failed to connect to client1:{tunnelPort}"

            try:
                # Send data through tunnel, receive echo from backend
                sentData = b"WORLD"
                receivedData, success = await conn.sendDataExpectEcho(sentData)

                assert success, "Failed to send and receive"
                assert (
                    b"WORLD" in receivedData
                ), "Response does not contain WORLD"
                logger.info(
                    "Test 1.2: Successfully validated client-to-server tunnel 1 echo"
                )
            finally:
                await conn.close()
        finally:
            await echoServer.close()

    @pytest.mark.asyncio
    async def test_1_3_combined_tunnels_tun1_sequential(self):
        """Test 1.3: Combined Tunnels (Tun1) Sequential"""
        portConfig = get_port_config()

        # Start echo servers for both backends
        serverEchoPort = portConfig.serverToClient1Tun1ConnectPort
        serverEchoServer = UtilTcpSocket(
            "server_echo_backend",
            shouldEchoData=True,
        )
        serverListening = await serverEchoServer.startListen(
            port=serverEchoPort, host="0.0.0.0"
        )
        assert (
            serverListening
        ), f"Failed to start server echo server on port {serverEchoPort}"

        clientEchoPort = portConfig.clientToServerTun1ConnectPort
        clientEchoServer = UtilTcpSocket(
            "client_echo_backend",
            shouldEchoData=True,
        )
        clientListening = await clientEchoServer.startListen(
            port=clientEchoPort, host="0.0.0.0"
        )
        assert (
            clientListening
        ), f"Failed to start client echo server on port {clientEchoPort}"

        try:
            # Test server tunnel first
            serverTunnelPort = portConfig.serverToClientTun1ListenPort
            serverConn = UtilTcpSocket("test_1_3_server")
            serverConnected = await serverConn.startConnect(
                "server", serverTunnelPort
            )
            assert (
                serverConnected
            ), f"Failed to connect to server:{serverTunnelPort}"

            try:
                sentData = b"SERVER"
                receivedData, success = await serverConn.sendDataExpectEcho(
                    sentData
                )
                assert success, "Failed to send and receive from server tunnel"
                assert (
                    b"SERVER" in receivedData
                ), "Server response does not contain SERVER"
            finally:
                await serverConn.close()

            # Test client tunnel
            clientTunnelPort = portConfig.client1ToServerTun1ListenPort
            clientConn = UtilTcpSocket("test_1_3_client")
            clientConnected = await clientConn.startConnect(
                "client1", clientTunnelPort
            )
            assert (
                clientConnected
            ), f"Failed to connect to client1:{clientTunnelPort}"

            try:
                sentData = b"CLIENT"
                receivedData, success = await clientConn.sendDataExpectEcho(
                    sentData
                )
                assert success, "Failed to send and receive from client tunnel"
                assert (
                    b"CLIENT" in receivedData
                ), "Client response does not contain CLIENT"
            finally:
                await clientConn.close()

            logger.info(
                "Test 1.3: Successfully validated combined tunnels sequential"
            )
        finally:
            await serverEchoServer.close()
            await clientEchoServer.close()

    @pytest.mark.asyncio
    async def test_1_4_both_tunnels_simultaneously(self):
        """Test 1.4: Both Tunnels Simultaneously"""
        portConfig = get_port_config()

        # Track connected clients for each echo server
        tun1_clients = []
        tun2_clients = []

        async def on_tun1_client_connected(clientId: int):
            tun1_clients.append(clientId)
            logger.debug(f"Tun1 echo server: client {clientId} connected")

        async def on_tun2_client_connected(clientId: int):
            tun2_clients.append(clientId)
            logger.debug(f"Tun2 echo server: client {clientId} connected")

        # Start echo servers for both tunnel backends
        tun1EchoPort = portConfig.serverToClient1Tun1ConnectPort
        tun1EchoServer = UtilTcpSocket(
            "tun1_echo_backend",
            shouldEchoData=True,
        )
        tun1EchoServer.setOnClientConnected(on_tun1_client_connected)
        tun1Listening = await tun1EchoServer.startListen(
            port=tun1EchoPort, host="0.0.0.0"
        )
        assert (
            tun1Listening
        ), f"Failed to start tun1 echo server on port {tun1EchoPort}"

        tun2EchoPort = portConfig.serverToClient1Tun2ConnectPort
        tun2EchoServer = UtilTcpSocket(
            "tun2_echo_backend",
            shouldEchoData=True,
        )
        tun2EchoServer.setOnClientConnected(on_tun2_client_connected)
        tun2Listening = await tun2EchoServer.startListen(
            port=tun2EchoPort, host="0.0.0.0"
        )
        assert (
            tun2Listening
        ), f"Failed to start tun2 echo server on port {tun2EchoPort}"

        try:
            # Connect to both tunnel endpoints
            tun1Port = portConfig.serverToClientTun1ListenPort
            tun2Port = portConfig.serverToClientTun2ListenPort
            conn1 = UtilTcpSocket("test_1_4_tun1")
            conn2 = UtilTcpSocket("test_1_4_tun2")

            connected1 = await conn1.startConnect("server", tun1Port)
            assert connected1, f"Failed to connect to server:{tun1Port}"

            connected2 = await conn2.startConnect("server", tun2Port)
            assert connected2, f"Failed to connect to server:{tun2Port}"

            try:
                # Send data simultaneously to both tunnels
                async def sendToTun1():
                    return await conn1.sendDataExpectEcho(b"TUN1")

                async def sendToTun2():
                    return await conn2.sendDataExpectEcho(b"TUN2")

                results = await asyncio.gather(sendToTun1(), sendToTun2())

                data1, success1 = results[0]
                data2, success2 = results[1]

                assert success1, "Failed to send and receive from tunnel 1"
                assert success2, "Failed to send and receive from tunnel 2"
                assert (
                    b"TUN1" in data1
                ), "Tunnel 1 response does not contain TUN1"
                assert (
                    b"TUN2" in data2
                ), "Tunnel 2 response does not contain TUN2"

                logger.info(
                    "Test 1.4: Successfully validated both tunnels simultaneously"
                )
            finally:
                await conn1.close()
                await conn2.close()
        finally:
            await tun1EchoServer.close()
            await tun2EchoServer.close()

    @pytest.mark.asyncio
    async def test_1_5_failover_event(self):
        """Test 1.5: Failover Event"""
        await triggerFailoverToClient2()

    @pytest.mark.asyncio
    async def test_1_6_server_to_client_tun1_echo_client2(self):
        """Test 1.6: Server-to-Client Tunnel 1 Echo (Client 2)"""
        portConfig = get_port_config()

        # Start echo server on client2 backend port
        echoPort = portConfig.serverToClient2Tun1ConnectPort
        echoServer = UtilTcpSocket(
            "echo_backend_c2",
            shouldEchoData=True,
        )
        listening = await echoServer.startListen(port=echoPort, host="0.0.0.0")
        assert listening, f"Failed to start echo server on port {echoPort}"

        try:
            # Connect to tunnel endpoint
            tunnelPort = portConfig.serverToClientTun1ListenPort
            conn = UtilTcpSocket("test_1_6")
            connected = await conn.startConnect("server", tunnelPort)
            assert connected, f"Failed to connect to server:{tunnelPort}"

            try:
                # Send data through tunnel, receive echo from backend
                sentData = b"HELLO"
                receivedData, success = await conn.sendDataExpectEcho(sentData)

                assert success, "Failed to send and receive"
                assert (
                    b"HELLO" in receivedData
                ), "Response does not contain HELLO"
                logger.info(
                    "Test 1.6: Successfully validated server-to-client tunnel 1 echo (client 2)"
                )
            finally:
                await conn.close()
        finally:
            await echoServer.close()

    @pytest.mark.asyncio
    async def test_1_7_client_to_server_tun1_echo_client2(self):
        """Test 1.7: Client-to-Server Tunnel 1 Echo (Client 2)"""
        portConfig = get_port_config()

        # Start echo server on shared backend port
        echoPort = portConfig.clientToServerTun1ConnectPort
        echoServer = UtilTcpSocket(
            "echo_backend_c2",
            shouldEchoData=True,
        )
        listening = await echoServer.startListen(port=echoPort, host="0.0.0.0")
        assert listening, f"Failed to start echo server on port {echoPort}"

        try:
            # Connect to client2 tunnel endpoint
            tunnelPort = portConfig.client2ToServerTun1ListenPort
            conn = UtilTcpSocket("test_1_7")
            connected = await conn.startConnect("client2", tunnelPort)
            assert connected, f"Failed to connect to client2:{tunnelPort}"

            try:
                # Send data through tunnel, receive echo from backend
                sentData = b"WORLD"
                receivedData, success = await conn.sendDataExpectEcho(sentData)

                assert success, "Failed to send and receive"
                assert (
                    b"WORLD" in receivedData
                ), "Response does not contain WORLD"
                logger.info(
                    "Test 1.7: Successfully validated client-to-server tunnel 1 echo (client 2)"
                )
            finally:
                await conn.close()
        finally:
            await echoServer.close()

    @pytest.mark.asyncio
    async def test_1_8_combined_tunnels_tun1_sequential_client2(self):
        """Test 1.8: Combined Tunnels (Tun1) Sequential (Client 2)"""
        portConfig = get_port_config()

        # Start echo servers for both backends
        serverEchoPort = portConfig.serverToClient2Tun1ConnectPort
        serverEchoServer = UtilTcpSocket(
            "server_echo_backend_c2",
            shouldEchoData=True,
        )
        serverListening = await serverEchoServer.startListen(
            port=serverEchoPort, host="0.0.0.0"
        )
        assert (
            serverListening
        ), f"Failed to start server echo server on port {serverEchoPort}"

        clientEchoPort = portConfig.clientToServerTun1ConnectPort
        clientEchoServer = UtilTcpSocket(
            "client_echo_backend_c2",
            shouldEchoData=True,
        )
        clientListening = await clientEchoServer.startListen(
            port=clientEchoPort, host="0.0.0.0"
        )
        assert (
            clientListening
        ), f"Failed to start client echo server on port {clientEchoPort}"

        try:
            # Test server tunnel first
            serverTunnelPort = portConfig.serverToClientTun1ListenPort
            serverConn = UtilTcpSocket("test_1_8_server")
            serverConnected = await serverConn.startConnect(
                "server", serverTunnelPort
            )
            assert (
                serverConnected
            ), f"Failed to connect to server:{serverTunnelPort}"

            try:
                sentData = b"SERVER"
                receivedData, success = await serverConn.sendDataExpectEcho(
                    sentData
                )
                assert success, "Failed to send and receive from server tunnel"
                assert (
                    b"SERVER" in receivedData
                ), "Server response does not contain SERVER"
            finally:
                await serverConn.close()

            # Test client tunnel
            clientTunnelPort = portConfig.client2ToServerTun1ListenPort
            clientConn = UtilTcpSocket("test_1_8_client")
            clientConnected = await clientConn.startConnect(
                "client2", clientTunnelPort
            )
            assert (
                clientConnected
            ), f"Failed to connect to client2:{clientTunnelPort}"

            try:
                sentData = b"CLIENT"
                receivedData, success = await clientConn.sendDataExpectEcho(
                    sentData
                )
                assert success, "Failed to send and receive from client tunnel"
                assert (
                    b"CLIENT" in receivedData
                ), "Client response does not contain CLIENT"
            finally:
                await clientConn.close()

            logger.info(
                "Test 1.8: Successfully validated combined tunnels sequential (client 2)"
            )
        finally:
            await serverEchoServer.close()
            await clientEchoServer.close()

    @pytest.mark.asyncio
    async def test_1_9_both_tunnels_simultaneously_client2(self):
        """Test 1.9: Both Tunnels Simultaneously (Client 2)"""
        portConfig = get_port_config()

        # Track connected clients for each echo server
        tun1_clients = []
        tun2_clients = []

        async def on_tun1_client_connected(clientId: int):
            tun1_clients.append(clientId)
            logger.debug(
                f"Tun1 echo server (client2): client {clientId} connected"
            )

        async def on_tun2_client_connected(clientId: int):
            tun2_clients.append(clientId)
            logger.debug(
                f"Tun2 echo server (client2): client {clientId} connected"
            )

        # Start echo servers for both tunnel backends
        tun1EchoPort = portConfig.serverToClient2Tun1ConnectPort
        tun1EchoServer = UtilTcpSocket(
            "tun1_echo_backend_c2",
            shouldEchoData=True,
        )
        tun1EchoServer.setOnClientConnected(on_tun1_client_connected)
        tun1Listening = await tun1EchoServer.startListen(
            port=tun1EchoPort, host="0.0.0.0"
        )
        assert (
            tun1Listening
        ), f"Failed to start tun1 echo server on port {tun1EchoPort}"

        tun2EchoPort = portConfig.serverToClient2Tun2ConnectPort
        tun2EchoServer = UtilTcpSocket(
            "tun2_echo_backend_c2",
            shouldEchoData=True,
        )
        tun2EchoServer.setOnClientConnected(on_tun2_client_connected)
        tun2Listening = await tun2EchoServer.startListen(
            port=tun2EchoPort, host="0.0.0.0"
        )
        assert (
            tun2Listening
        ), f"Failed to start tun2 echo server on port {tun2EchoPort}"

        try:
            # Connect to both tunnel endpoints
            tun1Port = portConfig.serverToClientTun1ListenPort
            tun2Port = portConfig.serverToClientTun2ListenPort
            conn1 = UtilTcpSocket("test_1_9_tun1")
            conn2 = UtilTcpSocket("test_1_9_tun2")

            connected1 = await conn1.startConnect("server", tun1Port)
            assert connected1, f"Failed to connect to server:{tun1Port}"

            connected2 = await conn2.startConnect("server", tun2Port)
            assert connected2, f"Failed to connect to server:{tun2Port}"

            try:
                # Send data simultaneously to both tunnels
                async def sendToTun1():
                    return await conn1.sendDataExpectEcho(b"TUN1")

                async def sendToTun2():
                    return await conn2.sendDataExpectEcho(b"TUN2")

                results = await asyncio.gather(sendToTun1(), sendToTun2())

                data1, success1 = results[0]
                data2, success2 = results[1]

                assert success1, "Failed to send and receive from tunnel 1"
                assert success2, "Failed to send and receive from tunnel 2"
                assert (
                    b"TUN1" in data1
                ), "Tunnel 1 response does not contain TUN1"
                assert (
                    b"TUN2" in data2
                ), "Tunnel 2 response does not contain TUN2"

                logger.info(
                    "Test 1.9: Successfully validated both tunnels simultaneously (client 2)"
                )
            finally:
                await conn1.close()
                await conn2.close()
        finally:
            await tun1EchoServer.close()
            await tun2EchoServer.close()
