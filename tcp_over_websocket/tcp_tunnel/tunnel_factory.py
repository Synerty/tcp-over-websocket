"""Factory for creating TCP protocol instances with connection management."""

import logging
from typing import Dict
from twisted.internet import protocol
from twisted.internet.defer import inlineCallbacks
from .tunnel_protocol import TunnelProtocol

logger = logging.getLogger(__name__)


class TunnelFactory(protocol.Factory):
    """Factory for creating TCP protocol instances with connection management.
    
    This factory creates protocol instances for handling individual TCP
    connections within a tunnel, providing connection lifecycle management
    and data routing capabilities.
    """

    def __init__(
        self,
        dataReceivedCallable,
        connectionMadeCallable,
        connectionLostCallable,
        tunnelName,
        connectionIdGenerator,
        onFirstDataReceivedCallback=None,
    ):
        """Initialize the factory with callbacks and configuration.
        
        Args:
            dataReceivedCallable: Function to call when data is received
            connectionMadeCallable: Function to call when connections are made
            connectionLostCallable: Function to call when connections are lost
            tunnelName: Name of the tunnel this factory serves
            connectionIdGenerator: Function that generates unique connection IDs
            onFirstDataReceivedCallback: Optional callback for first data received event
        """
        self._dataReceivedCallable = dataReceivedCallable
        self._connectionMadeCallable = connectionMadeCallable
        self._connectionLostCallable = connectionLostCallable
        self._tunnelName = tunnelName
        self._connectionIdGenerator = connectionIdGenerator
        self._onFirstDataReceivedCallback = onFirstDataReceivedCallback
        self._protocols: Dict[str, TunnelProtocol] = {}

    def buildProtocol(self, addr):
        """Build a new protocol instance for an incoming TCP connection.
        
        Args:
            addr: Address information for the connection
            
        Returns:
            TunnelProtocol: New protocol instance for handling the connection
        """
        connectionId = self._connectionIdGenerator()

        protocol = TunnelProtocol(
            self._dataReceivedCallable,
            self._connectionMadeCallable,
            self._connectionLostCallable,
            self._tunnelName,
            connectionId,
            self._onFirstDataReceivedCallback,
)

        self._protocols[connectionId] = protocol
        return protocol

    def write(self, data: bytes):
        """Write data to the most recent connection (backward compatibility).
        
        Args:
            data: Data to write to TCP connection
        """
        # Route to the most recent connection if no specific connection ID
        if self._protocols:
            # Get the most recently created protocol
            connectionId = max(self._protocols.keys())
            self._protocols[connectionId].write(data)
        else:
            logger.warning(
                f"Factory.write() called but no active protocols for [{self._tunnelName}]"
            )

    def writeToConnection(self, connectionId: str, data: bytes):
        """Write data to a specific connection.
        
        Args:
            connectionId: Target connection identifier
            data: Data to write to the connection
        """
        if connectionId in self._protocols:
            self._protocols[connectionId].write(data)
        else:
            logger.warning(
                f"No protocol found for connection [{connectionId}] in tunnel [{self._tunnelName}]"
            )

    @inlineCallbacks
    def closeConnection(self, connectionId: str):
        """Close a specific connection.
        
        Args:
            connectionId: Connection to close
        """
        if connectionId in self._protocols:
            protocol = self._protocols[connectionId]
            del self._protocols[connectionId]
            yield self._closeProtocol(protocol)

    @inlineCallbacks
    def closeAllConnections(self):
        """Close all active connections managed by this factory."""
        protocols = list(self._protocols.values())
        self._protocols.clear()

        for protocol in protocols:
            yield self._closeProtocol(protocol)

    @inlineCallbacks
    def _closeProtocol(self, protocol):
        """Close a single protocol instance.
        
        Args:
            protocol: Protocol instance to close
        """
        logger.debug(
            f"Disconnecting tcp connection"
            f" for [{self._tunnelName}] connection [{protocol._connectionId}]"
        )
        yield protocol.close()
        logger.debug(
            f"Disconnected tcp connection"
            f" for [{self._tunnelName}] connection [{protocol._connectionId}]"
        )