import logging

from twisted.internet import protocol
from twisted.internet import reactor
from twisted.internet.endpoints import TCP4ClientEndpoint
from vortex.DeferUtil import deferToThreadWrapWithLogger
from vortex.PayloadEndpoint import PayloadEndpoint
from vortex.PayloadEnvelope import PayloadEnvelope
from vortex.VortexFactory import VortexFactory

from tcp_over_websocket.config.file_config_tcp_connect_tunnel import (
    FileConfigTcpConnectTunnel,
)

logger = logging.getLogger(__name__)


class TcpTunnelConnect:
    def __init__(
        self, config: FileConfigTcpConnectTunnel, otherVortexName: str
    ):
        self._config = config
        self._otherVortexName = otherVortexName
        self._dataFilt = dict(key=config.tunnelName, data=True)

        self._factory = _ConnectFactory(self._processFromTcp)

        self._endpoint = None
        self._tcpClient = None

    def start(self):
        self._endpoint = PayloadEndpoint(
            dict(key=self._config.tunnelName), self._processFromVortex
        )

        self._tcpClient = TCP4ClientEndpoint(
            reactor,
            port=self._config.connectToPort,
            host=self._config.connectToHost,
        ).connect(self._factory)

    def shutdown(self):
        if self._endpoint:
            self._endpoint.shutdown()
            self._endpoint = None

        if self._tcpClient:
            self._tcpClient.close()
            self._tcpClient = None

    def _processFromVortex(
        self, payloadEnvelope: PayloadEnvelope, *args, **kwargs
    ):
        self._factory.write(payloadEnvelope.data)

    @deferToThreadWrapWithLogger(logger)
    def _processFromTcp(self, data: bytes):
        VortexFactory.sendVortexMsg(
            PayloadEnvelope(self._dataFilt, data=data).toVortexMsg(),
            destVortexName=self._otherVortexName,
        )


class _ConnectProtocol(protocol.Protocol):
    def __init__(self, dataReceivedCallable):
        self._dataReceivedCallable = dataReceivedCallable

    def dataReceived(self, data):
        self._dataReceivedCallable(data)

    def write(self, data: bytes):
        self.transport.write(data)

    def close(self):
        self.transport.loseConnection()


class _ConnectFactory(protocol.Factory):
    def __init__(self, dataReceivedCallable):
        self._dataReceivedCallable = dataReceivedCallable
        self._lastProtocol = None

    def buildProtocol(self, addr):
        if self._lastProtocol:
            self._lastProtocol.close()
        self._lastProtocol = _ConnectProtocol(self._dataReceivedCallable)
        return self._lastProtocol

    def write(self, data: bytes):
        assert self._lastProtocol, "We have no last protocol"
        self._lastProtocol.write(data)
