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

        logger.debug(f"Started tcp listen for [{self._tunnelName}]")
        self._tcpServer = yield endpoint.listen(self._factory)

    def shutdown(self):
        self._shutdown()

        if self._tcpServer:
            self._tcpServer.stopListening()
            self._tcpServer = None

        logger.debug(f"Stopped tcp listen for [{self._tunnelName}]")

    def _remoteConnectionMade(self):
        TcpTunnelABC._remoteConnectionMade(self)
        # Do nothing, all is good

    def _remoteConnectionLost(self, cleanly: bool):
        TcpTunnelABC._remoteConnectionLost(self, cleanly)

        # If the remote end can't connect, then drop the connection
        self._factory.closeLastConnection()
