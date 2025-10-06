import logging
from typing import Dict

from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks
from twisted.internet.endpoints import TCP4ServerEndpoint
from twisted.internet.interfaces import IListeningPort
from vortex.PayloadEndpoint import PayloadEndpoint
from vortex.PayloadEnvelope import PayloadEnvelope
from vortex.VortexFactory import VortexFactory

from tcp_over_websocket.config import file_config
from tcp_over_websocket.config.file_config_tcp_listen_tunnel import (
    FileConfigTcpListenTunnel,
)
from tcp_over_websocket.tcp_tunnel.tcp_tunnel_abc import TcpTunnelABC
from tcp_over_websocket.tcp_tunnel.tunnel_factory import TunnelFactory
from tcp_over_websocket.util.vortex_util import CLIENT_KILL_SIGNAL_FILT
from tcp_over_websocket.util.vortex_util import SERVER_VORTEX_NAME

logger = logging.getLogger(__name__)


class TcpTunnelListen(TcpTunnelABC):
    @property
    def side(self) -> str:
        return "listen"

    def __init__(
        self,
        config: FileConfigTcpListenTunnel,
        activeRemoteController,
        tunnelConnectionController=None,
    ):
        TcpTunnelABC.__init__(self, config.tunnelName, activeRemoteController)
        self._config = config
        self._tcpServers: Dict[str, IListeningPort] = {}
        self._tunnelConnectionController = tunnelConnectionController
        self._killSignalEndpoint = None

    @inlineCallbacks
    def start(self):
        yield None
        self._start()

        # Setup kill signal handler for clients (only for client-side instances)
        if not self._activeRemoteController.isServer:
            self._killSignalEndpoint = PayloadEndpoint(
                {
                    "key": CLIENT_KILL_SIGNAL_FILT,
                    "tunnel_name": self._tunnelName,
                },
                self._processKillSignal,
            )

        logger.info(
            f"Starting TCP listener for tunnel [{self._tunnelName}]"
            f" on {self._config.listenBindAddress}:{self._config.listenPort}"
        )

        # Create factory for this tunnel
        factory = TunnelFactory(
            self._processFromTcp,
            self._localConnectionMade,
            self._localConnectionLost,
            self._tunnelName,
            self._generateConnectionId,
            self._onFirstDataReceived,
)

        endpoint = TCP4ServerEndpoint(
            reactor,
            port=self._config.listenPort,
            interface=self._config.listenBindAddress,
        )

        self._tcpServers[self._tunnelName] = yield endpoint.listen(factory)
        logger.info(
            f"TCP listener started for tunnel [{self._tunnelName}]"
            f" on {self._config.listenBindAddress}:{self._config.listenPort}"
        )

    @inlineCallbacks
    def shutdown(self):
        self._shutdown()

        # Shutdown signal handlers
        if self._killSignalEndpoint:
            self._killSignalEndpoint.shutdown()
            self._killSignalEndpoint = None



        if self._tunnelName not in self._tcpServers:
            logger.debug(f"No tcp listen to stop for [{self._tunnelName}]")

        else:
            logger.debug(f"Stopping tcp listen for [{self._tunnelName}]")
            tcpServer = self._tcpServers[self._tunnelName]
            if tcpServer.connected:
                yield tcpServer.stopListening()
            del self._tcpServers[self._tunnelName]

            # Close existing connections
            yield self._closeAllConnections()

        logger.debug(f"Stopped tcp listen for [{self._tunnelName}]")

    def _onFirstDataReceived(self, protocol):
        """Handle first data received on a connection (triggers failover for clients)."""
        fileConfig = file_config.FileConfig()
        
        if not fileConfig.weAreServer and self._tunnelConnectionController:
            logger.debug(
                f"First data received on client {fileConfig.clientId} for tunnel [{self._tunnelName}]"
                f" connection [{protocol._connectionId}] - triggering failover"
            )
            self._tunnelConnectionController.recordTunnelConnection(
                fileConfig.clientId, self._tunnelName, protocol._connectionId
            )

    def _localConnectionMade(self, connectionId: str, protocol):
        # Call parent implementation
        return TcpTunnelABC._localConnectionMade(self, connectionId, protocol)

    @inlineCallbacks
    def _remoteConnectionMade(self, connectionId: str):
        yield TcpTunnelABC._remoteConnectionMade(self, connectionId)
        # Do nothing, all is good

    @inlineCallbacks
    def _remoteConnectionLost(self, connectionId: str, cleanly: bool):
        yield TcpTunnelABC._remoteConnectionLost(self, connectionId, cleanly)

        # If the remote end can't connect, then drop the specific connection
        yield self._closeConnection(connectionId)

    @inlineCallbacks
    def _processKillSignal(
        self, payloadEnvelope: PayloadEnvelope, *args, **kwargs
    ):
        """Process kill signal from server"""
        connectionId = payloadEnvelope.filt.get("connection_id")

        if connectionId:
            logger.info(
                f"Received kill signal for tunnel [{self._tunnelName}]"
                f" connection [{connectionId}]"
            )
            # Close specific connection
            yield self._closeConnection(connectionId)
        else:
            logger.info(
                f"Received kill signal for all connections in"
                f" tunnel [{self._tunnelName}]"
            )
            # Close all connections in this tunnel
            yield self._closeAllConnections()

        # Send acknowledgment back
        ackSignal = PayloadEnvelope(
            filt={
                "key": CLIENT_KILL_SIGNAL_FILT,
                "tunnel_name": self._tunnelName,
                "connection_id": connectionId,
                "client_id": payloadEnvelope.filt.get("client_id"),
            }
        ).toVortexMsg()

        VortexFactory.sendVortexMsg(
            ackSignal, destVortexName=SERVER_VORTEX_NAME
        )




