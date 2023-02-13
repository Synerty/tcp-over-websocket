import logging

from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks
from twisted.internet.endpoints import TCP4ClientEndpoint
from twisted.python.failure import Failure
from vortex.PayloadEndpoint import PayloadEndpoint

from tcp_over_websocket.config.file_config_tcp_connect_tunnel import (
    FileConfigTcpConnectTunnel,
)
from tcp_over_websocket.tcp_tunnel.tcp_tunnel_abc import TcpTunnelABC

logger = logging.getLogger(__name__)


class TcpTunnelConnect(TcpTunnelABC):
    side = "connect"

    def __init__(
        self, config: FileConfigTcpConnectTunnel, otherVortexName: str
    ):
        TcpTunnelABC.__init__(self, config.tunnelName, otherVortexName)
        self._config = config
        self._tcpClient = None

    def start(self):
        self._start()

    def shutdown(self):
        self._shutdown()
        self._closeClient()

    @inlineCallbacks
    def _remoteConnectionMade(self):
        TcpTunnelABC._remoteConnectionMade(self)
        yield self._connectClient()

    def _remoteConnectionLost(self, cleanly: bool):
        TcpTunnelABC._remoteConnectionLost(self, cleanly)
        self._closeClient()

    def _closeClient(self):
        if self._tcpClient:
            self._tcpClient.close()
            self._tcpClient = None

    @inlineCallbacks
    def _connectClient(self):
        logger.debug(f"Connecting tcp for [{self._tunnelName}]")

        # Give it a timeout of 3 seconds, if it can't accept a TCP connection
        # in that time, it's not operationally capable
        endpoint = TCP4ClientEndpoint(
            reactor,
            port=self._config.connectToPort,
            host=self._config.connectToHost,
            timeout=3,
        )
        try:
            self._tcpClient = yield endpoint.connect(self._factory)

        except Exception as e:
            logger.warning(
                f"Failed to connect tcp for" f" [{self._tunnelName}]"
            )
            logger.exception(e)
            # Tell the other end that we can't do it.
            self._localConnectionLost(Failure(e), failedToConnect=True)
