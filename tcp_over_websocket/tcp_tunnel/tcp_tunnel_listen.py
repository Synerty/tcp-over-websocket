import logging

from twisted.internet import protocol
from twisted.internet import reactor
from twisted.internet.endpoints import TCP4ServerEndpoint
from vortex.DeferUtil import deferToThreadWrapWithLogger
from vortex.PayloadEndpoint import PayloadEndpoint
from vortex.PayloadEnvelope import PayloadEnvelope
from vortex.VortexFactory import VortexFactory

from tcp_over_websocket.config.file_config_tcp_listen_tunnel import (
    FileConfigTcpListenTunnel,
)

logger = logging.getLogger(__name__)


class TcpTunnelListen:
    def __init__(self, config: FileConfigTcpListenTunnel, otherVortexName: str):
        self._config = config
        self._otherVortexName = otherVortexName
        self._dataFilt = dict(key=config.tunnelName, data=True)

        self._factory = _ListenFactory(self._processFromTcp)
        self._tcpServer = None
        self._endpoint = None

    def start(self):
        self._endpoint = PayloadEndpoint(
            dict(key=self._config.tunnelName), self._processFromVortex
        )

        self._tcpServer = TCP4ServerEndpoint(
            reactor,
            port=self._config.listenPort,
            interface=self._config.listenBindAddress,
        ).listen(self._factory)

    def shutdown(self):
        if self._endpoint:
            self._endpoint.shutdown()
            self._endpoint = None

        if self._tcpServer:
            self._tcpServer.close()
            self._tcpServer = None

    def _processFromVortex(
        self, payloadEnvelope: PayloadEnvelope, *args, **kwargs
    ):
        self._factory.write(payloadEnvelope.data)

    @deferToThreadWrapWithLogger(logger)
    def _processFromTcp(self, data: bytes):
        VortexFactory.sendVortexMsg(
            PayloadEnvelope(self._dataFilt, data=data).toVortexMsg(),
            vortexName=self._otherVortexName,
        )


class _ListenProtocol(protocol.Protocol):
    def __init__(self, dataReceivedCallable):
        self._dataReceivedCallable = dataReceivedCallable

    def dataReceived(self, data):
        self._dataReceivedCallable(data)

    def write(self, data: bytes):
        self.transport.write(data)


class _ListenFactory(protocol.Factory):
    def __init__(self, dataReceivedCallable):
        self._dataReceivedCallable = dataReceivedCallable
        self._lastProtocol = None

    def buildProtocol(self, addr):
        if self._lastProtocol:
            self._lastProtocol.loseConnection()
        self._lastProtocol = _ListenProtocol(self._dataReceivedCallable)
        return self._lastProtocol

    def write(self, data: bytes):
        assert self._lastProtocol, "We have no last protocol"
        self._lastProtocol.write(data)
