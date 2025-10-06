"""Active remote controller for managing client failover and connection routing.

This module implements the core high availability functionality for the TCP-over-WebSocket
service, managing which client is active and handling failover between clients.
"""

import logging
import time
from typing import Dict
from typing import Optional
from typing import Set

from rx.subjects import BehaviorSubject
from rx.subjects import Subject
from vortex.PayloadEndpoint import PayloadEndpoint
from vortex.PayloadEnvelope import PayloadEnvelope
from vortex.VortexFactory import VortexFactory

from tcp_over_websocket.util.vortex_util import CLIENT_ACTIVE_SIGNAL_FILT
from tcp_over_websocket.util.vortex_util import CLIENT_KILL_SIGNAL_FILT
from tcp_over_websocket.util.vortex_util import CLIENT_VORTEX_NAME_1
from tcp_over_websocket.util.vortex_util import CLIENT_VORTEX_NAME_2
from tcp_over_websocket.util.vortex_util import SERVER_VORTEX_NAME

logger = logging.getLogger(__name__)


class ActiveRemoteController:
    """Manages active client selection and failover for high availability.
    
    This controller implements the core logic for the TCP-over-WebSocket service's
    high availability functionality. It:
    
    - Tracks which of two clients is currently active (server-side)
    - Routes connections to the active client 
    - Handles failover when clients connect/disconnect
    - Manages standby client behavior (client-side)
    - Coordinates graceful failover with socket closure timing
    
    The controller uses reactive observables to emit state changes that
    other components can subscribe to for coordinated failover behavior.
    """
    
    def __init__(self, isServer: bool, clientId: Optional[int] = None):
        """Initialize the active remote controller.
        
        Args:
            isServer: True if this is the server instance, False for client
            clientId: Client ID (1 or 2) if this is a client instance, None for server
        """
        self.isServer = isServer
        self._clientId = clientId
        self._lastFailoverTime = 0
        self._failoverCooldownSecs = 2

        # Observable for active client changes (server-side)
        self._activeClientSubject = BehaviorSubject(None)
        # Observable for server online status (client-side)
        self._serverOnlineSubject = BehaviorSubject(False)
        # Observable for standby transitions (client-side)
        self._standbyTransitionSubject = Subject()

        if isServer:
            # Server manages multiple clients
            self._activeClientId: Optional[int] = None
            self._lastConnectionTime: Dict[int, float] = {1: 0, 2: 0}
            self._clientOnlineState: Dict[int, bool] = {1: False, 2: False}
            self._activeTunnels: Dict[int, Set[str]] = {1: set(), 2: set()}
            self._activeConnections: Dict[int, Dict[str, Set[str]]] = {
                1: {},
                2: {},
            }  # clientId -> tunnelName -> connectionIds
        else:
            # Client only manages connection to server
            self._serverOnline = False

        self._killSignalEndpoint: Optional[PayloadEndpoint] = None
        self._activeSignalEndpoint: Optional[PayloadEndpoint] = None

    @property
    def activeClientObservable(self):
        """Observable that emits active client ID changes (server-side).
        
        Returns:
            Observable: Emits the active client ID (1, 2, or None) when it changes
        """
        return self._activeClientSubject.as_observable()

    @property
    def serverOnlineObservable(self):
        """Observable that emits server online status changes (client-side).
        
        Returns:
            Observable: Emits boolean values when server connectivity changes
        """
        return self._serverOnlineSubject.as_observable()

    @property
    def standbyTransitionObservable(self):
        """Observable that emits standby transition events (client-side).
        
        Returns:
            Observable: Emits transition events when this client becomes standby
        """
        return self._standbyTransitionSubject.as_observable()

    def start(self):
        """Start the active remote controller and set up message endpoints."""
        if self.isServer:
            self._killSignalEndpoint = PayloadEndpoint(
                {"key": CLIENT_KILL_SIGNAL_FILT}, self._processKillSignal
            )
            self._activeSignalEndpoint = PayloadEndpoint(
                {"key": CLIENT_ACTIVE_SIGNAL_FILT}, self._processActiveSignal
            )
        else:
            # Client handles active signals centrally here
            self._activeSignalEndpoint = PayloadEndpoint(
                {"key": CLIENT_ACTIVE_SIGNAL_FILT},
                self._processActiveSignalClient,
            )
        logger.info(f"ActiveRemoteController started (server={self.isServer})")

    def shutdown(self):
        """Shutdown the active remote controller and clean up resources."""
        if self._killSignalEndpoint:
            self._killSignalEndpoint.shutdown()
            self._killSignalEndpoint = None
        if self._activeSignalEndpoint:
            self._activeSignalEndpoint.shutdown()
            self._activeSignalEndpoint = None

        # Complete observables
        if hasattr(self._activeClientSubject, "on_completed"):
            self._activeClientSubject.on_completed()
        if hasattr(self._serverOnlineSubject, "on_completed"):
            self._serverOnlineSubject.on_completed()
        if hasattr(self._standbyTransitionSubject, "on_completed"):
            self._standbyTransitionSubject.on_completed()

        logger.info("ActiveRemoteController shutdown")

    def getActiveRemoteVortexName(self) -> Optional[str]:
        """Get the vortex name for the active remote endpoint.
        
        Returns:
            Optional[str]: Vortex name for routing messages to the active remote,
                          or None if no active remote is available
        """
        if self.isServer:
            # Server returns active client vortex name
            if self._activeClientId == 1:
                return CLIENT_VORTEX_NAME_1
            elif self._activeClientId == 2:
                return CLIENT_VORTEX_NAME_2
            return None
        else:
            # Client always returns server vortex name if online
            return SERVER_VORTEX_NAME if self._serverOnline else None

    def setRemoteOnline(self, remoteId: int, online: bool):
        """Update remote online status and handle failover logic.
        
        Args:
            remoteId: Client ID (1 or 2) for server-side, ignored for client-side
            online: True if the remote is now online, False if offline
        """
        if self.isServer:
            self._clientOnlineState[remoteId] = online
            logger.info(f"Client {remoteId} online status: {online}")

            if not online and self._activeClientId == remoteId:
                # Active client went offline, switch to other client if available
                otherClientId = 2 if remoteId == 1 else 1
                if self._clientOnlineState[otherClientId]:
                    logger.info(
                        f"Active client {remoteId} went offline, switching to client {otherClientId}"
                    )
                    self._switchActiveClient(otherClientId)
                else:
                    logger.info(
                        f"Active client {remoteId} went offline, no other clients available"
                    )
                    self._activeClientId = None
                    self._activeClientSubject.on_next(None)
        else:
            # For clients, remoteId should be ignored, we only track server
            oldStatus = self._serverOnline
            self._serverOnline = online
            logger.info(f"Server online status: {online}")

            if oldStatus != online:
                self._serverOnlineSubject.on_next(online)

    def recordTunnelConnection(
        self,
        clientId: int,
        tunnelName: str,
        connectionId: str = None,
    ):
        """Record a new tunnel connection for a client (server-side only).
        
        This method tracks tunnel connections and determines when to switch
        the active client based on new connection activity.
        
        Args:
            clientId: ID of the client making the connection (1 or 2)
            tunnelName: Name of the tunnel being connected to
            connectionId: Optional unique identifier for this specific connection
        """
        if not self.isServer:
            logger.warning(
                "recordTunnelConnection called on client-side ActiveRemoteController"
            )
            return

        currentTime = time.time()
        self._lastConnectionTime[clientId] = currentTime
        self._activeTunnels[clientId].add(tunnelName)

        # Track individual connections
        if connectionId:
            if tunnelName not in self._activeConnections[clientId]:
                self._activeConnections[clientId][tunnelName] = set()
            self._activeConnections[clientId][tunnelName].add(connectionId)

        logger.debug(
            f"Tunnel connection recorded for client {clientId}, tunnel: {tunnelName}"
            + (f", connection: {connectionId}" if connectionId else "")
        )

        # Determine if we should trigger failover
        if self._activeClientId is None:
            # No active client yet, make this one active
            logger.info(f"Setting initial active client to {clientId}")
            self._switchActiveClient(clientId)

        elif connectionId is None:
            logger.debug(
                "No tcp tunnel connection id, this must have been "
                "called from a websocket reconnect"
            )

        elif self._activeClientId != clientId:
            # Different client is connecting - trigger failover
            logger.info(
                f"Tcp Tunnel Connection on client {clientId}"
                f" [{tunnelName}], triggering failover from"
                f" client {self._activeClientId} to client {clientId}"
            )
            self._switchActiveClient(clientId)

        else:
            # Same client connecting - just record the connection
            logger.debug(
                f"Client {clientId} connection recorded,"
                f" active client remains {self._activeClientId}"
            )

    def removeTunnelConnection(
        self, clientId: int, tunnelName: str, connectionId: str = None
    ):
        """Remove a tunnel connection for a client (server-side only).
        
        Args:
            clientId: ID of the client removing the connection (1 or 2)
            tunnelName: Name of the tunnel being disconnected from
            connectionId: Optional unique identifier for the specific connection
        """
        if not self.isServer:
            logger.warning(
                "removeTunnelConnection called on client-side ActiveRemoteController"
            )
            return

        if connectionId and tunnelName in self._activeConnections[clientId]:
            self._activeConnections[clientId][tunnelName].discard(connectionId)
            # Remove tunnel if no connections remain
            if not self._activeConnections[clientId][tunnelName]:
                del self._activeConnections[clientId][tunnelName]
                self._activeTunnels[clientId].discard(tunnelName)
        else:
            # Remove entire tunnel
            self._activeTunnels[clientId].discard(tunnelName)
            if tunnelName in self._activeConnections[clientId]:
                del self._activeConnections[clientId][tunnelName]

        logger.debug(
            f"Tunnel connection removed for client {clientId}, tunnel: {tunnelName}"
            + (f", connection: {connectionId}" if connectionId else "")
        )

    def getActiveClientId(self) -> Optional[int]:
        """Get the currently active client ID (server-side only).
        
        Returns:
            Optional[int]: Active client ID (1 or 2), or None if no client is active
        """
        if self.isServer:
            return self._activeClientId
        return None

    def isClientActive(self, clientId: int) -> bool:
        """Check if a client is the active client (server-side only).
        
        Args:
            clientId: Client ID to check (1 or 2)
            
        Returns:
            bool: True if the specified client is currently active
        """
        if self.isServer:
            return self._activeClientId == clientId
        return False

    def isServerOnline(self) -> bool:
        """Check if server is online (client-side only).
        
        Returns:
            bool: True if server connection is established
        """
        if not self.isServer:
            return self._serverOnline
        return False

    def triggerFailover(self, newActiveClientId: int, reason: str = "explicit"):
        """Explicitly trigger failover to a different client (server-side only).
        
        Args:
            newActiveClientId: Client ID (1 or 2) to make active
            reason: Description of why failover was triggered
        """
        if not self.isServer:
            logger.warning(
                "triggerFailover called on client-side ActiveRemoteController"
            )
            return

        if not self._clientOnlineState.get(newActiveClientId, False):
            logger.warning(
                f"Cannot failover to offline client {newActiveClientId}"
            )
            return

        currentTime = time.time()
        timeSinceLastFailover = currentTime - self._lastFailoverTime
        if timeSinceLastFailover < self._failoverCooldownSecs:
            logger.info(
                f"Failover cooldown active ({timeSinceLastFailover:.1f}s < {self._failoverCooldownSecs}s), "
                f"ignoring failover request to client {newActiveClientId}"
            )
            return

        logger.info(
            f"Explicit failover triggered ({reason}): switching active client"
            f" from {self._activeClientId} to {newActiveClientId}"
        )
        self._switchActiveClient(newActiveClientId)

    def _switchActiveClient(self, newActiveClientId: int):
        """Switch the active client and kill tunnels on the old active client (server-side only).
        
        Args:
            newActiveClientId: Client ID to make active (1 or 2)
        """
        if not self.isServer:
            return

        oldActiveClientId = self._activeClientId
        self._activeClientId = newActiveClientId
        self._lastFailoverTime = time.time()

        if oldActiveClientId != newActiveClientId:
            logger.info(
                f"FAILOVER TRIGGERED: switching active client from"
                f" {oldActiveClientId} to {newActiveClientId}"
            )

            if oldActiveClientId:
                # Kill all tunnels on the previously active client
                logger.info(f"Killing tunnels on previous active client {oldActiveClientId}")
                self._killClientTunnels(oldActiveClientId)
            
            # Clear connection tracking for both clients to ensure clean state
            logger.info("Clearing all connection tracking on failover")
            self._activeTunnels[1].clear()
            self._activeTunnels[2].clear()
            self._activeConnections[1].clear()
            self._activeConnections[2].clear()
            
            # Notify new active client
            logger.info(f"Notifying client {newActiveClientId} it is now active")
            self._notifyClientActive(newActiveClientId)
        else:
            logger.debug(f"Client {newActiveClientId} was already active, no failover needed")
            # Still notify clients to ensure consistent state
            self._notifyClientActive(newActiveClientId)

        logger.info(f"Active client is now: {newActiveClientId}")

        # Emit observable change
        self._activeClientSubject.on_next(newActiveClientId)

    def _killClientTunnels(self, clientId: int):
        """Send kill signal to all tunnels on a client (server-side only).
        
        Args:
            clientId: Client ID whose tunnels should be killed (1 or 2)
        """
        if not self.isServer or not self._clientOnlineState[clientId]:
            return

        clientVortexName = (
            CLIENT_VORTEX_NAME_1 if clientId == 1 else CLIENT_VORTEX_NAME_2
        )

        # Kill individual connections
        totalConnections = 0
        activeConnections = dict(self._activeConnections[clientId])  # Create snapshot
        
        for tunnelName, connectionIds in activeConnections.items():
            connectionSet = set(connectionIds)  # Create snapshot of connection IDs
            logger.info(f"Sending kill signals for tunnel {tunnelName} with {len(connectionSet)} connections")
            for connectionId in connectionSet:
                killSignal = PayloadEnvelope(
                    filt={
                        "key": CLIENT_KILL_SIGNAL_FILT,
                        "tunnel_name": tunnelName,
                        "connection_id": connectionId,
                        "client_id": clientId,
                    }
                ).toVortexMsg()

                VortexFactory.sendVortexMsg(
                    killSignal, destVortexName=clientVortexName
                )
                logger.debug(f"Kill signal sent for connection {connectionId} on tunnel {tunnelName}")
                totalConnections += 1

        tunnelNames = list(activeConnections.keys())
        logger.info(
            f"FAILOVER: Kill signals sent to client {clientId} for {totalConnections} connections across {len(tunnelNames)} tunnels: {tunnelNames}"
        )

        # Clear the tunnel tracking for this client completely
        logger.debug(f"Clearing tunnel tracking for client {clientId}")
        self._activeTunnels[clientId].clear()
        self._activeConnections[clientId].clear()
        logger.debug(f"Tunnel tracking cleared for client {clientId}")

    def _notifyClientActive(self, clientId: int):
        """Notify client that it is now active (server-side only).
        
        Args:
            clientId: Client ID that is becoming active (1 or 2)
        """
        if not self.isServer:
            return

        activeSignal = PayloadEnvelope(
            filt={
                "key": CLIENT_ACTIVE_SIGNAL_FILT,
                "client_id": clientId,
                "timestamp": time.time(),
            }
        ).toVortexMsg()

        # Send signal to ALL online clients so standby clients know to become standby
        for targetClientId in [1, 2]:
            if self._clientOnlineState[targetClientId]:
                targetVortexName = (
                    CLIENT_VORTEX_NAME_1
                    if targetClientId == 1
                    else CLIENT_VORTEX_NAME_2
                )
                VortexFactory.sendVortexMsg(
                    activeSignal, destVortexName=targetVortexName
                )

        logger.info(
            f"Active signal sent to all online clients about client {clientId} becoming active"
        )

    def _processKillSignal(
        self, payloadEnvelope: PayloadEnvelope, *args, **kwargs
    ):
        """Process kill signal acknowledgment from clients (server-side only).
        
        Args:
            payloadEnvelope: Message containing kill signal acknowledgment
        """
        if not self.isServer:
            return

        tunnelName = payloadEnvelope.filt.get("tunnel_name")
        connectionId = payloadEnvelope.filt.get("connection_id")
        clientId = payloadEnvelope.filt.get("client_id")

        if tunnelName and clientId:
            if connectionId:
                logger.info(
                    f"Kill signal acknowledged for client {clientId}, tunnel: {tunnelName}, connection: {connectionId}"
                )
            else:
                logger.info(
                    f"Kill signal acknowledged for client {clientId}, tunnel: {tunnelName} (all connections)"
                )

    def _processActiveSignal(
        self, payloadEnvelope: PayloadEnvelope, *args, **kwargs
    ):
        """Process active signal acknowledgment from clients (server-side only).
        
        Args:
            payloadEnvelope: Message containing active signal acknowledgment
        """
        if not self.isServer:
            return

        clientId = payloadEnvelope.filt.get("client_id")

        if clientId:
            logger.debug(f"Active signal acknowledged by client {clientId}")

    def _processActiveSignalClient(
        self, payloadEnvelope: PayloadEnvelope, *args, **kwargs
    ):
        """Process active signal from server (client-side only).
        
        Args:
            payloadEnvelope: Message from server about active client changes
        """
        if self.isServer:
            return

        clientId = payloadEnvelope.filt.get("client_id")
        logger.info(f"Received active signal - client {clientId} is now active")

        # Send acknowledgment back
        ackSignal = PayloadEnvelope(
            filt={"key": CLIENT_ACTIVE_SIGNAL_FILT, "client_id": clientId}
        ).toVortexMsg()

        VortexFactory.sendVortexMsg(
            ackSignal, destVortexName=SERVER_VORTEX_NAME
        )

        # If this client is becoming standby (another client became active)
        if self._clientId != clientId:
            logger.info(
                f"This client (ID: {self._clientId}) is becoming standby, emitting transition event"
            )
            self._standbyTransitionSubject.on_next(
                {
                    "active_client_id": clientId,
                    "timestamp": time.time(),
                    "transition_type": "becoming_standby",
                }
            )