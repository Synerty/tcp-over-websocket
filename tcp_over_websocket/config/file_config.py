"""Main configuration class for TCP-over-WebSocket service.

This module provides the primary configuration interface that orchestrates
all configuration aspects including client identification, tunnel settings,
data exchange parameters, and logging configuration.
"""

from jsoncfg.value_mappers import require_array
from jsoncfg.value_mappers import require_bool

from tcp_over_websocket.config.file_config_abc import FileConfigABC
from tcp_over_websocket.config.file_config_data_exchange import (
    FileConfigDataExchange,
)
from tcp_over_websocket.config.file_config_service import FileConfigLogging
from tcp_over_websocket.config.file_config_tcp_connect_tunnel import (
    FileConfigTcpConnectTunnel,
)
from tcp_over_websocket.config.file_config_tcp_listen_tunnel import (
    FileConfigTcpListenTunnel,
)


class FileConfig(FileConfigABC):
    """Main configuration class that orchestrates all service settings.
    
    This class provides access to all configuration aspects of the TCP-over-WebSocket
    service, including:
    - Client identification for high availability setup
    - Server/client mode determination
    - TCP tunnel configurations (listen and connect)
    - WebSocket and security settings
    - Logging configuration
    - Failover timing settings
    
    The configuration is loaded from a JSON file and provides typed access
    to all settings with appropriate defaults.
    """
    
    @property
    def clientId(self) -> int:
        """Get the client ID for high availability setup.
        
        Returns:
            int: Client identifier (1 or 2) used for active/standby configuration.
                 Must be exactly 1 or 2 for proper failover functionality.
        
        Raises:
            AssertionError: If clientId is not 1 or 2.
        """
        with self._cfg as c:
            val = c.clientId(1)
            assert val in (1, 2), "Client ID must be 1 or 2"
            return val

    @property
    def weAreServer(self) -> bool:
        """Determine if this instance should run as a server.
        
        Returns:
            bool: True if this instance is the central server that routes
                  between clients, False if this is a client instance.
        """
        with self._cfg as c:
            return c.weAreServer(False, require_bool)

    @property
    def tcpTunnelListens(self) -> list:
        """Get list of TCP tunnel listen configurations.
        
        These are ports that this instance will bind to and listen for
        incoming TCP connections, which will then be tunneled through
        the WebSocket connection.
        
        Returns:
            list[FileConfigTcpListenTunnel]: List of tunnel listen configurations,
                each specifying tunnel name, listen port, and bind address.
        """
        with self._cfg as c:
            return [
                FileConfigTcpListenTunnel(self._cfg, node)
                for node in c.tcpTunnelListens([], require_array)
            ]

    @property
    def tcpTunnelConnects(self) -> list:
        """Get list of TCP tunnel connect configurations.
        
        These are outbound connections that this instance will establish
        when data comes through the corresponding WebSocket tunnel.
        
        Returns:
            list[FileConfigTcpConnectTunnel]: List of tunnel connect configurations,
                each specifying tunnel name, target host, and target port.
        """
        with self._cfg as c:
            return [
                FileConfigTcpConnectTunnel(self._cfg, node)
                for node in c.tcpTunnelConnects([], require_array)
            ]

    @property
    def dataExchange(self) -> FileConfigDataExchange:
        """Get WebSocket and security configuration.
        
        Returns:
            FileConfigDataExchange: Configuration for WebSocket connections,
                including server URL, SSL/TLS settings, and mutual TLS configuration.
        """
        return FileConfigDataExchange(self._cfg)

    @property
    def standbySocketCloseDurationSecs(self) -> int:
        """Get the duration to keep standby client sockets closed during failover.
        
        During active client transitions, the standby client will close its
        listening sockets for this duration to ensure clean failover and
        prevent connection conflicts.
        
        Returns:
            int: Duration in seconds (default: 15) to keep sockets closed
                 during failover transitions.
        """
        with self._cfg as c:
            return c.standbySocketCloseDurationSecs(15)

    @property
    def logging(self) -> FileConfigLogging:
        """Get logging configuration.
        
        Returns:
            FileConfigLogging: Configuration for log levels, output destinations,
                file rotation, and syslog integration.
        """
        return FileConfigLogging(self._cfg)