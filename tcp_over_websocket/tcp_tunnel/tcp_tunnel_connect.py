import logging

from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks
from twisted.internet.endpoints import TCP4ClientEndpoint
from twisted.python.failure import Failure

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
        logger.debug(f"Started tcp connect for [{self._tunnelName}]")

    @inlineCallbacks
    def shutdown(self):
        self._shutdown()
        yield self._closeClient()

    @inlineCallbacks
    def _remoteConnectionMade(self):
        yield TcpTunnelABC._remoteConnectionMade(self)
        yield self._connectClient()

    @inlineCallbacks
    def _remoteConnectionLost(self, cleanly: bool):
        yield TcpTunnelABC._remoteConnectionLost(self, cleanly)
        yield self._closeClient()

    @inlineCallbacks
    def _closeClient(self):
        if self._tcpClient:
            logger.debug(f"Stopping tcp connect for [{self._tunnelName}]")
            yield self._tcpClient.close()
            self._tcpClient = None

        else:
            logger.debug(f"No tcp connect to stop for [{self._tunnelName}]")

        logger.debug(f"Stopped tcp connect for [{self._tunnelName}]")

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
