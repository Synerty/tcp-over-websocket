import logging
import struct
from abc import ABCMeta
from collections import deque

from twisted.internet import protocol
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks
from twisted.internet.protocol import connectionDone
from twisted.python.failure import Failure
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
            self._tunnelName,
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
        tunnelName,
    ):
        self._dataReceivedCallable = dataReceivedCallable
        self._connectionMadeCallable = connectionMadeCallable
        self._connectionLostCallable = connectionLostCallable
        self._tunnelName = tunnelName
        self._sendPacketSequence = 1
        self._receivedPacketSequence = 1
        self._receivedDataBySequence: dict[int, bytes] = {}

    def connectionMade(self):
        try:
            self._connectionMadeCallable()
        except Exception as e:
            logger.exception(e)

    def connectionLost(self, reason: Failure = connectionDone):
        logger.debug(
            "Final SEND SEQ %s for [%s]",
            self._sendPacketSequence,
            self._tunnelName,
        )
        logger.debug(
            "Final RECEIVED SEQ %s for [%s]",
            self._receivedPacketSequence,
            self._tunnelName,
        )

        try:
            self._connectionLostCallable(reason)
        except Exception as e:
            logger.exception(e)

    def dataReceived(self, data):
        try:
            data = struct.pack("!Q", self._sendPacketSequence) + data
            self._dataReceivedCallable(data)
            self._sendPacketSequence += 1

        except Exception as e:
            logger.exception(e)

    def write(self, data: bytes):
        """Write

        This is us receiving data from the vortex, and sending it to the
        socket
        """
        seq = struct.unpack("!Q", data[:8])[0]
        data = data[8:]
        self._receivedDataBySequence[seq] = data
        if seq != self._receivedPacketSequence:
            logger.debug(
                "Received out of order package %s, expected %s, "
                "correcting it for [%s]",
                seq,
                self._receivedPacketSequence,
                self._tunnelName,
            )

        while self._receivedPacketSequence in self._receivedDataBySequence:
            data = self._receivedDataBySequence.pop(
                self._receivedPacketSequence
            )
            self._receivedPacketSequence += 1

            try:
                self.transport.write(data)
            except Exception as e:
                logger.exception(e)
                self.transport.loseConnection()

        if len(self._receivedDataBySequence) == 1000:
            logger.error(
                "Missing sequence %s, it's not turned up after 1000"
                " packets, for [%s]",
                self._receivedPacketSequence,
                self._tunnelName,
            )
            self.transport.loseConnection()

    @inlineCallbacks
    def close(self):
        try:
            logger.debug(f"Closing tcp connect for [{self._tunnelName}]")
            yield self.transport.loseConnection()
            logger.debug(f"Closed tcp connect for [{self._tunnelName}]")
        except Exception as e:
            logger.exception(
                "There was an issue with closing the TCP"
                " connection for [%s]. Exception: %s",
                self._tunnelName,
                e,
            )


class _ABCFactory(protocol.Factory):
    def __init__(
        self,
        dataReceivedCallable,
        connectionMadeCallable,
        connectionLostCallable,
        tunnelName,
    ):
        self._dataReceivedCallable = dataReceivedCallable
        self._connectionMadeCallable = connectionMadeCallable
        self._connectionLostCallable = connectionLostCallable
        self._tunnelName = tunnelName
        self._lastProtocol = None

    def buildProtocol(self, addr):
        if self._lastProtocol:
            reactor.callLater(0, self._closeProtocol, self._lastProtocol)
        self._lastProtocol = _ABCProtocol(
            self._dataReceivedCallable,
            self._connectionMadeCallable,
            self._connectionLostCallable,
            self._tunnelName,
        )
        return self._lastProtocol

    def write(self, data: bytes):
        assert self._lastProtocol, "We have no last protocol"
        self._lastProtocol.write(data)

    @inlineCallbacks
    def closeLastConnection(self):
        if self._lastProtocol:
            protocol = self._lastProtocol
            self._lastProtocol = None
            yield self._closeProtocol(protocol)

    @inlineCallbacks
    def _closeProtocol(self, protocol):
        logger.debug(
            f"Disconnecting existing tcp connections"
            f" for [{self._tunnelName}]"
        )
        yield protocol.close()
        logger.debug(
            f"Disconnected existing tcp connections"
            f" for [{self._tunnelName}]"
        )
