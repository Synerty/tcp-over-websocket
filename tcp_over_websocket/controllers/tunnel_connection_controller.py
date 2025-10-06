import logging
import time
from typing import Optional

from rx.subjects import Subject
from twisted.internet import reactor
from vortex.PayloadEndpoint import PayloadEndpoint
from vortex.PayloadEnvelope import PayloadEnvelope
from vortex.VortexFactory import VortexFactory

logger = logging.getLogger(__name__)

TUNNEL_CONNECTION_SIGNAL_FILT = "tunnel_connection_signal"


class TunnelConnectionController:
    """Tracks tunnel connections to determine active client"""

    def __init__(self, activeRemoteController):
        self._activeRemoteController = activeRemoteController
        self._connectionSignalEndpoint: Optional[PayloadEndpoint] = None
        self._isServer = False

        # Observable for connection events
        self._connectionSubject = Subject()

    @property
    def connectionObservable(self):
        """Observable that emits connection events"""
        return self._connectionSubject.as_observable()

    def start(self, isServer: bool):
        """Start the tunnel connection controller"""
        self._isServer = isServer

        if isServer:
            # Server listens for connection signals from clients
            self._connectionSignalEndpoint = PayloadEndpoint(
                {"key": TUNNEL_CONNECTION_SIGNAL_FILT},
                self._processConnectionSignal,
            )

        logger.info(f"TunnelConnectionController started (server={isServer})")

    def shutdown(self):
        """Shutdown the tunnel connection controller"""
        if self._connectionSignalEndpoint:
            self._connectionSignalEndpoint.shutdown()
            self._connectionSignalEndpoint = None

        # Complete observable
        if hasattr(self._connectionSubject, "on_completed"):
            self._connectionSubject.on_completed()

        logger.info("TunnelConnectionController shutdown")

    def recordTunnelConnection(
        self, clientId: int, tunnelName: str, connectionId: str = None
    ):
        """Record a tunnel connection and notify server if we're a client"""
        if not self._isServer:
            # Client sends signal to server about new connection
            self._sendConnectionSignal(clientId, tunnelName, connectionId)

        # Emit connection event
        self._connectionSubject.on_next(
            {
                "client_id": clientId,
                "tunnel_name": tunnelName,
                "connection_id": connectionId,
                "timestamp": time.time(),
            }
        )

    def _sendConnectionSignal(
        self, clientId: int, tunnelName: str, connectionId: str = None
    ):
        """Send connection signal to server"""
        signalFilt = {
            "key": TUNNEL_CONNECTION_SIGNAL_FILT,
            "client_id": clientId,
            "tunnel_name": tunnelName,
            "timestamp": time.time(),
        }

        if connectionId:
            signalFilt["connection_id"] = connectionId

        connectionSignal = PayloadEnvelope(filt=signalFilt).toVortexMsg()

        # Get the correct destination vortex name from activeRemoteController
        destVortexName = (
            self._activeRemoteController.getActiveRemoteVortexName()
        )
        if not destVortexName:
            logger.warning(
                f"No active remote available for connection signal"
                f" - client {clientId}, tunnel: {tunnelName}"
            )
            return

        # Delay signal slightly to ensure server tunnel handlers are ready
        reactor.callLater(
            0.1,
            lambda: VortexFactory.sendVortexMsg(
                connectionSignal, destVortexName=destVortexName
            ),
        )

        logger.debug(
            f"Connection signal queued to server"
            f" - client {clientId}, tunnel: {tunnelName}"
            + (f", connection: {connectionId}" if connectionId else "")
        )

    def _processConnectionSignal(
        self, payloadEnvelope: PayloadEnvelope, *args, **kwargs
    ):
        """Process connection signal from clients (server side)"""
        clientId = payloadEnvelope.filt.get("client_id")
        tunnelName = payloadEnvelope.filt.get("tunnel_name")
        connectionId = payloadEnvelope.filt.get("connection_id")

        if clientId and tunnelName and self._activeRemoteController:
            logger.debug(
                f"Received connection signal from"
                f" client {clientId}, tunnel: {tunnelName}"
                + (f", connection: {connectionId}" if connectionId else "")
            )
            self._activeRemoteController.recordTunnelConnection(
                clientId, tunnelName, connectionId
            )

            # Emit connection event
            self._connectionSubject.on_next(
                {
                    "client_id": clientId,
                    "tunnel_name": tunnelName,
                    "connection_id": connectionId,
                    "timestamp": payloadEnvelope.filt.get("timestamp"),
                }
            )
