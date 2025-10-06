import logging

from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks
from twisted.internet.endpoints import TCP4ClientEndpoint
from twisted.python.failure import Failure
from vortex.PayloadEnvelope import PayloadEnvelope
from vortex.VortexFactory import VortexFactory

from tcp_over_websocket.config.file_config_tcp_connect_tunnel import (
    FileConfigTcpConnectTunnel,
)
from tcp_over_websocket.tcp_tunnel.tcp_tunnel_abc import TcpTunnelABC
from tcp_over_websocket.tcp_tunnel.tunnel_factory import TunnelFactory
from tcp_over_websocket.util.vortex_util import CLIENT_VORTEX_NAME_1
from tcp_over_websocket.util.vortex_util import CLIENT_VORTEX_NAME_2

logger = logging.getLogger(__name__)


class TcpTunnelConnect(TcpTunnelABC):
    @property
    def side(self) -> str:
        return "connect"

    def __init__(
        self,
        config: FileConfigTcpConnectTunnel,
        activeRemoteController,
    ):
        TcpTunnelABC.__init__(self, config.tunnelName, activeRemoteController)
        self._config = config
        # Track active client connections by connection ID
        self._connectionClients = {}

    def start(self):
        self._start()
        logger.debug(f"Started tcp connect for [{self._tunnelName}]")

    @inlineCallbacks
    def shutdown(self):
        self._shutdown()
        yield self._closeAllClients()

    @inlineCallbacks
    def _remoteConnectionMade(self, connectionId: str):
        yield TcpTunnelABC._remoteConnectionMade(self, connectionId)

        # For server, check if we should route to active client
        if self._activeRemoteController.isServer:
            clientVortexName = {
                "C1": CLIENT_VORTEX_NAME_1,
                "C2": CLIENT_VORTEX_NAME_2,
            }[connectionId.split(".")[0]]
            # Update the routing for this specific connection
            self._connectionClients[connectionId] = clientVortexName
            logger.debug(
                f"Routing tunnel [{self._tunnelName}]"
                f" connection [{connectionId}]"
                f" to active client: {clientVortexName}"
            )

        yield self._connectClient(connectionId)

    @inlineCallbacks
    def _remoteConnectionLost(self, connectionId: str, cleanly: bool):
        yield TcpTunnelABC._remoteConnectionLost(self, connectionId, cleanly)
        yield self._closeClient(connectionId)

    @inlineCallbacks
    def _closeClient(self, connectionId: str):
        yield None
        if connectionId in self._activeConnections:
            protocol = self._activeConnections[connectionId]
            logger.debug(
                f"Stopping tcp connect for [{self._tunnelName}] connection [{connectionId}]"
            )
            # Remove from active connections first to prevent duplicate processing
            del self._activeConnections[connectionId]

            # Close using the protocol's transport (all our protocols have transport)
            if protocol.transport:
                protocol.transport.loseConnection()

        # Clean up client routing info
        if connectionId in self._connectionClients:
            del self._connectionClients[connectionId]

        logger.debug(
            f"Stopped tcp connect for [{self._tunnelName}] connection [{connectionId}]"
        )

    @inlineCallbacks
    def _closeAllClients(self):
        """Close all client connections"""
        connectionIds = list(self._activeConnections.keys())
        for connectionId in connectionIds:
            yield self._closeClient(connectionId)

    @inlineCallbacks
    def _connectClient(self, connectionId: str):
        logger.debug(
            f"Connecting tcp for [{self._tunnelName}] connection [{connectionId}]"
            f" to {self._config.connectToHost}:{self._config.connectToPort}"
        )

        # Give it a timeout of 3 seconds, if it can't accept a TCP connection
        # in that time, it's not operationally capable
        endpoint = TCP4ClientEndpoint(
            reactor,
            port=self._config.connectToPort,
            host=self._config.connectToHost,
            timeout=3,
        )
        try:
            # Create factory for this specific connection
            factory = TunnelFactory(
                self._processFromTcp,
                self._localConnectionMade,
                self._localConnectionLost,
                self._tunnelName,
                lambda: connectionId,  # Return the specific connectionId
                self._onFirstDataReceived,
            )

            protocol = yield endpoint.connect(factory)
            self._activeConnections[connectionId] = protocol

        except Exception as e:
            if "refused" in str(e).lower():
                logger.warning(
                    f"Connection was refused by remote service for [{self._tunnelName}]"
                    f" connection [{connectionId}]"
                    f" to {self._config.connectToHost}:{self._config.connectToPort}: {e}"
                )
            else:
                logger.error(
                    f"Failed to connect tcp for [{self._tunnelName}]"
                    f" connection [{connectionId}]"
                    f" to {self._config.connectToHost}:{self._config.connectToPort}: {e}"
                )
            # Tell the other end that we can't do it.
            self._localConnectionLost(
                connectionId, Failure(e), failedToConnect=True
            )

    def _send(self, filt, data=None):
        """Override send to route to correct client for server connections"""
        connectionId = filt.get("connection_id")

        if not self._activeRemoteController.isServer:
            targetVortexName = (
                self._activeRemoteController.getActiveRemoteVortexName()
            )
        else:
            # For server mode, use the connection id (C1.123, C2.123) to match
            # that to the vortex name to send the data back. This is correct
            # because the failover logic can happen after the data is returning
            # due to the order vortex websocket messages arrive
            if connectionId and connectionId in self._connectionClients:
                # Use cached routing for this specific connection
                targetVortexName = self._connectionClients[connectionId]
            else:
                # Fall back to active remote for new connections
                targetVortexName = (
                    self._activeRemoteController.getActiveRemoteVortexName()
                )
                # Update connection routing cache for this connection
                if connectionId and targetVortexName:
                    self._connectionClients[connectionId] = targetVortexName

        if not targetVortexName:
            logger.warning(
                f"No active remote available for tunnel [{self._tunnelName}]"
            )
            return

        # This is intentionally blocking, to ensure data is in sequence
        vortexMsg = PayloadEnvelope(filt, data=data).toVortexMsg()

        VortexFactory.sendVortexMsg(
            vortexMsg,
            destVortexName=targetVortexName,
        )

    def _onFirstDataReceived(self, protocol):
        """Handle first data received on a connection (no-op for connect side)."""
        pass
