"""TCP protocol implementation with packet sequencing for tunneling."""

import logging
import struct
from twisted.internet import protocol
from twisted.internet.defer import inlineCallbacks
from twisted.internet.protocol import connectionDone
from twisted.python.failure import Failure

logger = logging.getLogger(__name__)


class TunnelProtocol(protocol.Protocol):
    """TCP protocol implementation with packet sequencing for tunneling.

    This protocol handles TCP connections on one side of the tunnel,
    ensuring proper packet ordering when data is transmitted through
    the potentially unordered WebSocket transport layer.
    """

    def __init__(
        self,
        dataReceivedCallable,
        connectionMadeCallable,
        connectionLostCallable,
        tunnelName,
        connectionId,
        onFirstDataReceivedCallback=None,
    ):
        """Initialize the protocol with callbacks and sequencing state.
        
        Args:
            dataReceivedCallable: Function to call when data is received from TCP
            connectionMadeCallable: Function to call when TCP connection is established
            connectionLostCallable: Function to call when TCP connection is lost
            tunnelName: Name of the tunnel this protocol belongs to
            connectionId: Unique identifier for this connection
            onFirstDataReceivedCallback: Optional callback for first data received event
        """
        self._dataReceivedCallable = dataReceivedCallable
        self._connectionMadeCallable = connectionMadeCallable
        self._connectionLostCallable = connectionLostCallable
        self._tunnelName = tunnelName
        self._connectionId = connectionId
        self._onFirstDataReceivedCallback = onFirstDataReceivedCallback
        self._sendPacketSequence = 1
        self._receivedPacketSequence = 1
        self._receivedDataBySequence: dict[int, bytes] = {}
        self._hasSentData = False

    def connectionMade(self):
        """Handle TCP connection establishment."""
        try:
            self._connectionMadeCallable(self._connectionId, self)
        except Exception as e:
            logger.exception(e)

    def connectionLost(self, reason: Failure = connectionDone):
        """Handle TCP connection termination.

        Args:
            reason: Reason for connection termination
        """
        logger.debug(
            "Final SEND SEQ %s for [%s] connection [%s]",
            self._sendPacketSequence,
            self._tunnelName,
            self._connectionId,
        )
        logger.debug(
            "Final RECEIVED SEQ %s for [%s] connection [%s]",
            self._receivedPacketSequence,
            self._tunnelName,
            self._connectionId,
        )

        try:
            self._connectionLostCallable(self._connectionId, reason)
        except Exception as e:
            logger.exception(e)

    def dataReceived(self, data):
        """Handle data received from TCP connection.

        Adds sequence number to data before forwarding through tunnel.
        On first data received, triggers failover if this is a client connection.

        Args:
            data: Raw bytes received from TCP connection
        """
        try:
            # Handle first data received logic (for failover, etc.)
            if not self._hasSentData:
                if self._onFirstDataReceivedCallback:
                    self._onFirstDataReceivedCallback(self)
                self._hasSentData = True

            data = struct.pack("!Q", self._sendPacketSequence) + data
            self._dataReceivedCallable(self._connectionId, data)
            self._sendPacketSequence += 1

        except Exception as e:
            logger.exception(e)

    def write(self, data: bytes):
        """Write data received from WebSocket tunnel to TCP connection.

        Handles packet sequencing to ensure data is delivered to TCP
        in the correct order even if WebSocket packets arrive out of sequence.

        Args:
            data: Sequenced data from WebSocket tunnel (sequence number + payload)
        """
        seq = struct.unpack("!Q", data[:8])[0]
        data = data[8:]
        self._receivedDataBySequence[seq] = data
        if seq != self._receivedPacketSequence:
            logger.debug(
                "Received out of order package %s, expected %s, "
                "correcting it for [%s] connection [%s]",
                seq,
                self._receivedPacketSequence,
                self._tunnelName,
                self._connectionId,
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

        if len(self._receivedDataBySequence) == 100:
            logger.error(
                "Missing sequence %s, it's not turned up after 100"
                " packets, for [%s] connection [%s]",
                self._receivedPacketSequence,
                self._tunnelName,
                self._connectionId,
            )
            self.transport.loseConnection()

    @inlineCallbacks
    def close(self):
        """Gracefully close the TCP connection.

        Yields:
            Deferred that completes when connection is closed
        """
        try:
            logger.debug(
                f"Closing tcp connect for [{self._tunnelName}] connection [{self._connectionId}]"
            )
            yield self.transport.loseConnection()
            logger.debug(
                f"Closed tcp connect for [{self._tunnelName}] connection [{self._connectionId}]"
            )
        except Exception as e:
            logger.exception(
                "There was an issue with closing the TCP"
                " connection for [%s] connection [%s]. Exception: %s",
                self._tunnelName,
                self._connectionId,
                e,
            )
