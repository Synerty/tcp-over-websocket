import logging
from abc import ABCMeta
from abc import abstractmethod
from collections import deque

from twisted.internet import protocol
from twisted.internet import reactor
from twisted.internet.defer import Deferred
from twisted.internet.defer import inlineCallbacks
from twisted.internet.protocol import connectionDone
from twisted.internet.task import deferLater
from twisted.python.failure import Failure
from vortex.DeferUtil import vortexLogFailure
from vortex.PayloadEndpoint import PayloadEndpoint
from vortex.PayloadEnvelope import PayloadEnvelope
from vortex.VortexFactory import VortexFactory


logger = logging.getLogger(__name__)

FILT_IS_DATA_KEY = "is_data"
FILT_IS_CONTROL_KEY = "is_control"
FILT_CONTROL_KEY = "control"
FILT_CONTROL_MADE_VALUE = "made"
FILT_CONTROL_LOST_VALUE = "lost"
FILT_CONTROL_CLOSED_CLEANLY_VALUE = "closed_cleanly"


class TcpTunnelABC(metaclass=ABCMeta):
    side = None

    def __init__(self, tunnelName: str, otherVortexName: str):
        self._tunnelName = tunnelName
        self._otherVortexName = otherVortexName

        self._listenFilt = dict(key=tunnelName)

        self._sendDataFilt = {FILT_IS_DATA_KEY: True}
        self._sendDataFilt.update(self._listenFilt)

        self._sendControlFilt = {FILT_IS_CONTROL_KEY: True}
        self._sendControlFilt.update(self._listenFilt)

        self._factory = _ABCFactory(
            self._processFromTcp,
            self._localConnectionMade,
            self._localConnectionLost,
        )
        self._tcpServer = None
        self._endpoint = None

        self._isLocalConnected = False
        self._dataBuffer: deque[bytes] = deque()

    def _start(self):
        self._endpoint = PayloadEndpoint(
            self._listenFilt, self._processFromVortex
        )

    def _shutdown(self):
        if self._endpoint:
            self._endpoint.shutdown()
            self._endpoint = None

    @inlineCallbacks
    def _processFromVortex(
        self, payloadEnvelope: PayloadEnvelope, *args, **kwargs
    ):
        if payloadEnvelope.filt.get(FILT_IS_DATA_KEY):
            if payloadEnvelope.data:
                if self._isLocalConnected:
                    self._factory.write(payloadEnvelope.data)
                else:
                    self._dataBuffer.append(payloadEnvelope.data)
            return

        assert payloadEnvelope.filt.get(
            FILT_IS_CONTROL_KEY
        ), "We received an unknown payloadEnvelope"

        method = {
            FILT_CONTROL_MADE_VALUE: self._remoteConnectionMade,
            FILT_CONTROL_LOST_VALUE: lambda: self._remoteConnectionLost(
                cleanly=False
            ),
            FILT_CONTROL_CLOSED_CLEANLY_VALUE: lambda: self._remoteConnectionLost(
                cleanly=True
            ),
        }

        control = payloadEnvelope.filt[FILT_CONTROL_KEY]
        assert control in method, "We received an unknown control command"
        yield method[control]()

    def _processFromTcp(self, data: bytes):
        self._send(self._sendDataFilt, data=data)

    def _send(self, filt, data=None):
        # This is intentionally blocking, to ensure data is in sequence
        vortexMsg = PayloadEnvelope(filt, data=data).toVortexMsg()

        VortexFactory.sendVortexMsg(
            vortexMsg,
            destVortexName=self._otherVortexName,
        )

    def _localConnectionMade(self):
        logger.debug(
            f"Local tcp {self.side} connection made"
            f" for [{self._tunnelName}]"
        )
        filt = {FILT_CONTROL_KEY: FILT_CONTROL_MADE_VALUE}
        filt.update(self._sendControlFilt)
        # Give any data a chance to be sent
        self._isLocalConnected = True
        while self._dataBuffer:
            self._factory.write(self._dataBuffer.popleft())
        self._send(filt)

    def _localConnectionLost(self, reason: Failure, failedToConnect=False):
        self._isLocalConnected = False
        if not failedToConnect:
            if reason == connectionDone or reason.value is None:
                logger.debug(
                    f"Local tcp {self.side} connection closed cleanly"
                    f" for [{self._tunnelName}]"
                )
            else:
                logger.debug(
                    f"Local tcp {self.side} connection lost"
                    f" for [{self._tunnelName}],"
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
        # Give any data a chance to be sent
        self._send(filt)

    def _remoteConnectionMade(self):
        logger.debug(
            f"Remote of tcp {self.side} connection made"
            f" for [{self._tunnelName}]"
        )

    def _remoteConnectionLost(self, cleanly: bool):
        if cleanly:
            logger.debug(
                f"Remote of tcp {self.side} connection closed cleanly"
                f" for"
                f" [{self._tunnelName}]"
            )
        else:
            logger.debug(
                f"Remote of tcp {self.side} connection lost"
                f" for [{self._tunnelName}]"
            )


class _ABCProtocol(protocol.Protocol):
    def __init__(
        self,
        dataReceivedCallable,
        connectionMadeCallable,
        connectionLostCallable,
    ):
        self._dataReceivedCallable = dataReceivedCallable
        self._connectionMadeCallable = connectionMadeCallable
        self._connectionLostCallable = connectionLostCallable

    def connectionMade(self):
        try:
            self._connectionMadeCallable()
        except Exception as e:
            logger.exception(e)

    def connectionLost(self, reason: Failure = connectionDone):
        try:
            self._connectionLostCallable(reason)
        except Exception as e:
            logger.exception(e)

    def dataReceived(self, data):
        try:
            self._dataReceivedCallable(data)
        except Exception as e:
            logger.exception(e)

    def write(self, data: bytes):
        try:
            self.transport.write(data)
        except Exception as e:
            logger.exception(e)

    def close(self):
        try:
            self.transport.loseConnection()
        except Exception as e:
            logger.exception(e)


class _ABCFactory(protocol.Factory):
    def __init__(
        self,
        dataReceivedCallable,
        connectionMadeCallable,
        connectionLostCallable,
    ):
        self._dataReceivedCallable = dataReceivedCallable
        self._connectionMadeCallable = connectionMadeCallable
        self._connectionLostCallable = connectionLostCallable
        self._lastProtocol = None

    def buildProtocol(self, addr):
        self.closeLastConnection()
        self._lastProtocol = _ABCProtocol(
            self._dataReceivedCallable,
            self._connectionMadeCallable,
            self._connectionLostCallable,
        )
        return self._lastProtocol

    def write(self, data: bytes):
        assert self._lastProtocol, "We have no last protocol"
        self._lastProtocol.write(data)

    def closeLastConnection(self):
        if self._lastProtocol:
            self._lastProtocol.close()
            self._lastProtocol = None
