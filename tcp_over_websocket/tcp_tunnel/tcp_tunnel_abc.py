"""Abstract base class for TCP tunnel implementations.

This module provides the core tunneling logic that bridges TCP connections
with WebSocket communication, including packet sequencing, connection management,
and bidirectional data flow.
"""

import logging
from abc import ABCMeta
from abc import abstractmethod
from collections import deque
from typing import Dict

from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks
from twisted.internet.protocol import connectionDone
from twisted.python.failure import Failure
from vortex.PayloadEndpoint import PayloadEndpoint
from vortex.PayloadEnvelope import PayloadEnvelope
from vortex.VortexFactory import VortexFactory

from .tunnel_protocol import TunnelProtocol


logger = logging.getLogger(__name__)

FILT_IS_DATA_KEY = "is_data"
FILT_IS_CONTROL_KEY = "is_control"
FILT_CONTROL_KEY = "control"
FILT_CONNECTION_ID_KEY = "connection_id"
FILT_CONTROL_MADE_VALUE = "made"
FILT_CONTROL_LOST_VALUE = "lost"
FILT_CONTROL_CLOSED_CLEANLY_VALUE = "closed_cleanly"


class GlobalConnectionCounter:
    """Global connection counter to ensure unique connection IDs across all tunnels."""
    _instance = None
    _counter = 0

    @classmethod
    def getInstance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def getNextConnectionNumber(cls) -> int:
        """Get the next unique connection number across all tunnels."""
        instance = cls.getInstance()
        instance._counter += 1
        return instance._counter


class TcpTunnelABC(metaclass=ABCMeta):
    """Abstract base class for TCP tunneling over WebSocket connections.

    This class implements the core logic for tunneling TCP traffic through
    WebSocket connections with the following features:

    - Packet sequencing to ensure data ordering over WebSocket transport
    - Connection lifecycle management (made/lost/closed events)
    - Bidirectional data flow between TCP and WebSocket endpoints
    - Connection multiplexing with unique connection IDs
    - Data buffering for out-of-sequence packets

    Subclasses implement either listen-side or connect-side tunnel behavior.
    """

    @property
    @abstractmethod
    def side(self) -> str:
        """Get the tunnel side identifier.

        Returns:
            str: Either 'listen' or 'connect' to identify tunnel type
        """

    def __init__(self, tunnelName: str, activeRemoteController):
        """Initialize the TCP tunnel.

        Args:
            tunnelName: Unique identifier for this tunnel
            activeRemoteController: Controller for managing active remote endpoints
        """
        self._tunnelName = tunnelName
        self._activeRemoteController = activeRemoteController
        self._connectionIdPrefix = self._generateConnectionIdPrefix()
        self._activeConnections: Dict[str, "TunnelProtocol"] = {}

        self._listenFilt = dict(key=tunnelName)

        self._sendDataFilt = {FILT_IS_DATA_KEY: True}
        self._sendDataFilt.update(self._listenFilt)

        self._sendControlFilt = {FILT_IS_CONTROL_KEY: True}
        self._sendControlFilt.update(self._listenFilt)

        self._endpoint = None

        self._connectionDataBuffers: Dict[str, deque[bytes]] = {}

    def _generateConnectionIdPrefix(self) -> str:
        """Generate connection ID prefix based on component type and client ID.

        Returns:
            str: Prefix for connection IDs ("S" for server, "C1"/"C2" for clients)
        """
        from tcp_over_websocket.config import file_config

        try:
            fileConfig = file_config.FileConfig()

            if fileConfig.weAreServer:
                return "S"
            else:
                return f"C{fileConfig.clientId}"
        except:
            # Fallback if config is not available
            return "C1"

    def _generateConnectionId(self) -> str:
        """Generate a unique connection ID with proper prefix.

        Returns:
            str: Unique connection ID in format "PREFIX.COUNTER"
        """
        connectionNumber = GlobalConnectionCounter.getNextConnectionNumber()
        return f"{self._connectionIdPrefix}.{connectionNumber}"

    def _start(self):
        """Start the tunnel endpoint for receiving WebSocket messages."""
        self._endpoint = PayloadEndpoint(
            self._listenFilt, self._processFromVortex
        )

    def _shutdown(self):
        """Shutdown the tunnel endpoint and clean up resources."""
        if self._endpoint:
            self._endpoint.shutdown()
            self._endpoint = None

    @inlineCallbacks
    def _processFromVortex(
        self, payloadEnvelope: PayloadEnvelope, *args, **kwargs
    ):
        """Process incoming messages from WebSocket/Vortex layer.

        Handles both data packets and control messages (connection lifecycle events).
        Data packets are routed to the appropriate TCP connection, while control
        messages trigger connection management actions.

        Args:
            payloadEnvelope: Message containing data or control information
        """
        connectionId = payloadEnvelope.filt.get(FILT_CONNECTION_ID_KEY)

        if payloadEnvelope.filt.get(FILT_IS_DATA_KEY):
            if payloadEnvelope.data and connectionId:
                if connectionId in self._activeConnections:
                    self._activeConnections[connectionId].write(
                        payloadEnvelope.data
                    )
                else:
                    # Buffer data for connections that haven't been established yet
                    if connectionId not in self._connectionDataBuffers:
                        self._connectionDataBuffers[connectionId] = deque()
                    self._connectionDataBuffers[connectionId].append(
                        payloadEnvelope.data
                    )
            return

        assert payloadEnvelope.filt.get(
            FILT_IS_CONTROL_KEY
        ), "We received an unknown payloadEnvelope"

        method = {
            FILT_CONTROL_MADE_VALUE: lambda: self._remoteConnectionMade(
                connectionId
            ),
            FILT_CONTROL_LOST_VALUE: lambda: self._remoteConnectionLost(
                connectionId, cleanly=False
            ),
            FILT_CONTROL_CLOSED_CLEANLY_VALUE: lambda: self._remoteConnectionLost(
                connectionId, cleanly=True
            ),
        }

        control = payloadEnvelope.filt[FILT_CONTROL_KEY]
        assert control in method, "We received an unknown control command"
        yield method[control]()

    def _processFromTcp(self, connectionId: str, data: bytes):
        """Process data received from TCP connection for transmission over WebSocket.

        Args:
            connectionId: Unique identifier for the TCP connection
            data: Raw bytes received from TCP connection
        """
        filt = dict(self._sendDataFilt)
        filt[FILT_CONNECTION_ID_KEY] = connectionId
        self._send(filt, data=data)

    def _send(self, filt, data=None):
        """Send data or control messages over WebSocket to remote endpoint.

        Args:
            filt: Message filter/routing information
            data: Optional data payload to send
        """
        # This is intentionally blocking, to ensure data is in sequence
        vortexMsg = PayloadEnvelope(filt, data=data).toVortexMsg()

        remoteVortexName = (
            self._activeRemoteController.getActiveRemoteVortexName()
        )
        if remoteVortexName:
            VortexFactory.sendVortexMsg(
                vortexMsg,
                destVortexName=remoteVortexName,
            )
        else:
            logger.warning(
                f"No active remote available for tunnel [{self._tunnelName}]"
            )

    def _localConnectionMade(
        self, connectionId: str, protocol: "TunnelProtocol"
    ):
        """Handle new local TCP connection establishment.

        Registers the connection, sends buffered data if any exists,
        and notifies the remote endpoint about the new connection.

        Args:
            connectionId: Unique identifier for this connection
            protocol: Protocol instance handling the TCP connection
        """
        logger.debug(
            f"Local tcp {self.side} connection made"
            f" for [{self._tunnelName}] connection [{connectionId}]"
        )

        self._activeConnections[connectionId] = protocol

        # Send any buffered data for this connection
        if connectionId in self._connectionDataBuffers:
            while self._connectionDataBuffers[connectionId]:
                protocol.write(
                    self._connectionDataBuffers[connectionId].popleft()
                )
            del self._connectionDataBuffers[connectionId]

        filt = {FILT_CONTROL_KEY: FILT_CONTROL_MADE_VALUE}
        filt.update(self._sendControlFilt)
        filt[FILT_CONNECTION_ID_KEY] = connectionId
        self._send(filt)

    def _localConnectionLost(
        self, connectionId: str, reason: Failure, failedToConnect=False
    ):
        """Handle local TCP connection termination.

        Cleans up connection state and notifies remote endpoint about
        the connection closure.

        Args:
            connectionId: Unique identifier for the closed connection
            reason: Reason for connection termination
            failedToConnect: True if connection failed to establish initially
        """
        # Clean up connection state
        if connectionId in self._activeConnections:
            del self._activeConnections[connectionId]

        # Clean up any buffered data
        if connectionId in self._connectionDataBuffers:
            del self._connectionDataBuffers[connectionId]

        if not failedToConnect:
            if reason == connectionDone or reason.value is None:
                logger.debug(
                    f"Local tcp {self.side} connection closed cleanly"
                    f" for [{self._tunnelName}] connection [{connectionId}]"
                )
            else:
                logger.debug(
                    f"Local tcp {self.side} connection lost"
                    f" for [{self._tunnelName}] connection [{connectionId}],"
                    f" reason={reason.getErrorMessage()}"
                )

        filt = {
            FILT_CONTROL_KEY: (
                FILT_CONTROL_CLOSED_CLEANLY_VALUE
                if reason == connectionDone or reason.value is None
                else FILT_CONTROL_LOST_VALUE
            )
        }
        filt.update(self._sendControlFilt)
        filt[FILT_CONNECTION_ID_KEY] = connectionId
        self._send(filt)

    def _remoteConnectionMade(self, connectionId: str):
        """Handle remote TCP connection establishment notification.

        Called when the remote endpoint successfully establishes
        its corresponding TCP connection.

        Args:
            connectionId: Unique identifier for the remote connection
        """
        logger.debug(
            f"Remote of tcp {self.side} connection made"
            f" for [{self._tunnelName}] connection [{connectionId}]"
        )

    def _remoteConnectionLost(self, connectionId: str, cleanly: bool):
        """Handle remote TCP connection termination notification.

        Closes the corresponding local TCP connection when the
        remote endpoint reports connection termination.

        Args:
            connectionId: Unique identifier for the remote connection
            cleanly: True if remote connection closed cleanly
        """
        if cleanly:
            logger.debug(
                f"Remote of tcp {self.side} connection closed cleanly"
                f" for [{self._tunnelName}] connection [{connectionId}]"
            )
        else:
            logger.debug(
                f"Remote of tcp {self.side} connection lost"
                f" for [{self._tunnelName}] connection [{connectionId}]"
            )

        # Close the local connection for this specific connection ID
        if connectionId in self._activeConnections:
            protocol = self._activeConnections[connectionId]
            # Remove from active connections immediately to prevent duplicate processing
            del self._activeConnections[connectionId]

            # Clean up any buffered data
            if connectionId in self._connectionDataBuffers:
                del self._connectionDataBuffers[connectionId]

            # Close using the protocol's transport (all our protocols have transport)
            if protocol.transport:
                reactor.callLater(0, protocol.transport.loseConnection)

    @inlineCallbacks
    def _closeConnection(self, connectionId: str):
        """Close a specific connection.

        Args:
            connectionId: Unique identifier for connection to close
        """
        yield None
        if connectionId in self._activeConnections:
            protocol = self._activeConnections[connectionId]
            del self._activeConnections[connectionId]

            # Clean up any buffered data
            if connectionId in self._connectionDataBuffers:
                del self._connectionDataBuffers[connectionId]

            logger.debug(
                f"Closing tcp {self.side} for [{self._tunnelName}] connection [{connectionId}]"
            )

            # Close using the protocol's transport (all our protocols have transport)
            if protocol.transport:
                protocol.transport.loseConnection()

            logger.debug(
                f"Closed tcp {self.side} for [{self._tunnelName}] connection [{connectionId}]"
            )

    @abstractmethod
    def _onFirstDataReceived(self, protocol):
        """Handle first data received on a connection (for failover logic).

        Args:
            protocol: The protocol instance that received the first data
        """
        pass

    @inlineCallbacks
    def _closeAllConnections(self):
        """Close all active connections for this tunnel."""
        connectionIds = list(self._activeConnections.keys())
        for connectionId in connectionIds:
            yield self._closeConnection(connectionId)
