import logging

from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks
from twisted.internet.endpoints import TCP4ServerEndpoint

from tcp_over_websocket.config.file_config_tcp_listen_tunnel import (
    FileConfigTcpListenTunnel,
)
from tcp_over_websocket.tcp_tunnel.tcp_tunnel_abc import TcpTunnelABC

logger = logging.getLogger(__name__)


class TcpTunnelListen(TcpTunnelABC):
    side = "listen"

    def __init__(self, config: FileConfigTcpListenTunnel, otherVortexName: str):
        TcpTunnelABC.__init__(self, config.tunnelName, otherVortexName)
        self._config = config
        self._tcpServer = None

    @inlineCallbacks
    def start(self):
        self._start()

        endpoint = TCP4ServerEndpoint(
            reactor,
            port=self._config.listenPort,
            interface=self._config.listenBindAddress,
        )

        self._tcpServer = yield endpoint.listen(self._factory)
        logger.debug(f"Started tcp listen for [{self._tunnelName}]")

    @inlineCallbacks
    def shutdown(self):
        self._shutdown()

        if self._tcpServer:
            logger.debug(f"Stopping tcp listen for [{self._tunnelName}]")
            yield self._tcpServer.stopListening()
            self._tcpServer = None

            # Close existing connections
            yield self._factory.closeLastConnection()

        else:
            logger.debug(f"No tcp listen to stop for [{self._tunnelName}]")

        logger.debug(f"Stopped tcp listen for [{self._tunnelName}]")

    @inlineCallbacks
    def _remoteConnectionMade(self):
        yield TcpTunnelABC._remoteConnectionMade(self)
        # Do nothing, all is good

    @inlineCallbacks
    def _remoteConnectionLost(self, cleanly: bool):
        yield TcpTunnelABC._remoteConnectionLost(self, cleanly)

        # If the remote end can't connect, then drop the connection
        yield self._factory.closeLastConnection()
