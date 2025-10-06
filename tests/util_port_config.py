import json
import logging
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)


class PortConfig:
    """Port configuration parser that reads from config files and provides standardized port access"""

    def __init__(self):
        self.config_base_dir = Path(__file__).parent.parent / "test_config"

        self._server_config = None
        self._client1_config = None
        self._client2_config = None
        self._load_configs()

    def _load_configs(self):
        """Load all configuration files"""
        server_config_file = (
            self.config_base_dir / "websocket_server" / "config.json"
        )
        client1_config_file = (
            self.config_base_dir / "websocket_client_1" / "config.json"
        )
        client2_config_file = (
            self.config_base_dir / "websocket_client_2" / "config.json"
        )

        with open(server_config_file, "r") as f:
            self._server_config = json.load(f)

        with open(client1_config_file, "r") as f:
            self._client1_config = json.load(f)

        with open(client2_config_file, "r") as f:
            self._client2_config = json.load(f)

    def get_server_websocket_port(self) -> int:
        """Get server WebSocket port (from dataExchange.serverUrl)"""
        server_url = self._server_config["dataExchange"]["serverUrl"]
        # Extract port from URL
        if ":" in server_url:
            port_str = server_url.split(":")[-1]
            return int(port_str)
        raise ValueError("No port found in server URL")

    def get_server_tunnel_ports(self) -> Dict[str, int]:
        """Get server tunnel listen ports"""
        ports = {}
        for tunnel in self._server_config["tcpTunnelListens"]:
            tunnel_name = tunnel["tunnelName"]
            port = tunnel["listenPort"]
            ports[tunnel_name] = port
        return ports

    def get_client1_tunnel_ports(self) -> Dict[str, int]:
        """Get client 1 tunnel listen ports"""
        ports = {}
        for tunnel in self._client1_config["tcpTunnelListens"]:
            tunnel_name = tunnel["tunnelName"]
            port = tunnel["listenPort"]
            ports[tunnel_name] = port
        return ports

    def get_client2_tunnel_ports(self) -> Dict[str, int]:
        """Get client 2 tunnel listen ports"""
        ports = {}
        for tunnel in self._client2_config["tcpTunnelListens"]:
            tunnel_name = tunnel["tunnelName"]
            port = tunnel["listenPort"]
            ports[tunnel_name] = port
        return ports

    def get_test_server_ports(self) -> Dict[str, int]:
        """Get test echo server ports (derived from connect configurations)"""
        test_ports = {}

        # Get ports from server connects (where server connects to test servers)
        for tunnel in self._server_config["tcpTunnelConnects"]:
            tunnel_name = tunnel["tunnelName"]
            port = tunnel["connectToPort"]
            test_ports[f"test_{tunnel_name}"] = port

        # Get ports from client connects (where clients connect to test servers)
        for client_config in [self._client1_config, self._client2_config]:
            for tunnel in client_config["tcpTunnelConnects"]:
                tunnel_name = tunnel["tunnelName"]
                port = tunnel["connectToPort"]
                test_ports[f"test_{tunnel_name}"] = port

        return test_ports

    # Convenience methods for common port access patterns
    def server_port(self, tunnel_name: str) -> int:
        """Get server port by tunnel name"""
        ports = self.get_server_tunnel_ports()
        return ports[tunnel_name]

    def client1_port(self, tunnel_name: str) -> int:
        """Get client 1 port by tunnel name"""
        ports = self.get_client1_tunnel_ports()
        return ports[tunnel_name]

    def client2_port(self, tunnel_name: str) -> int:
        """Get client 2 port by tunnel name"""
        ports = self.get_client2_tunnel_ports()
        return ports[tunnel_name]

    def test_port(self, test_name: str) -> int:
        """Get test server port by test name"""
        ports = self.get_test_server_ports()
        return ports[test_name]

    # CamelCase properties with descriptive names - Server WebSocket Port
    @property
    def serverWebsocketPort(self) -> int:
        """Server WebSocket port for client connections"""
        return self.get_server_websocket_port()

    # CamelCase properties with descriptive names - Server Tunnel Listen Ports
    @property
    def serverToClientTun1ListenPort(self) -> int:
        """Server listen port for server-to-client tunnel 1 (routes to active client backend)"""
        return self.server_port("server-to-client-tun1")

    @property
    def serverToClientTun2ListenPort(self) -> int:
        """Server listen port for server-to-client tunnel 2 (routes to active client backend)"""
        return self.server_port("server-to-client-tun2")

    # CamelCase properties with descriptive names - Client Tunnel Listen Ports
    @property
    def client1ToServerTun1ListenPort(self) -> int:
        """Client 1 listen port for client-to-server tunnel 1"""
        return self.client1_port("client-to-server-tun1")

    @property
    def client1ToServerTun2ListenPort(self) -> int:
        """Client 1 listen port for client-to-server tunnel 2"""
        port = self.client1_port("client-to-server-tun2")
        logger.debug(f"client1ToServerTun2ListenPort returning: {port}")
        return port

    @property
    def client2ToServerTun1ListenPort(self) -> int:
        """Client 2 listen port for client-to-server tunnel 1"""
        return self.client2_port("client-to-server-tun1")

    @property
    def client2ToServerTun2ListenPort(self) -> int:
        """Client 2 listen port for client-to-server tunnel 2"""
        return self.client2_port("client-to-server-tun2")

    # CamelCase properties with descriptive names - Test Echo Server Connect Ports
    @property
    def serverToClient1Tun1ConnectPort(self) -> int:
        """Server to Client 1 tunnel 1 connect port (server-to-client-tun1 destination for client 1)"""
        for tunnel in self._client1_config["tcpTunnelConnects"]:
            if tunnel["tunnelName"] == "server-to-client-tun1":
                return tunnel["connectToPort"]
        raise ValueError(
            "Server to Client 1 tunnel 1 connect port not found in config"
        )

    @property
    def serverToClient1Tun2ConnectPort(self) -> int:
        """Server to Client 1 tunnel 2 connect port (server-to-client-tun2 destination for client 1)"""
        for tunnel in self._client1_config["tcpTunnelConnects"]:
            if tunnel["tunnelName"] == "server-to-client-tun2":
                return tunnel["connectToPort"]
        raise ValueError(
            "Server to Client 1 tunnel 2 connect port not found in config"
        )

    @property
    def serverToClient2Tun1ConnectPort(self) -> int:
        """Server to Client 2 tunnel 1 connect port (server-to-client-tun1 destination for client 2)"""
        for tunnel in self._client2_config["tcpTunnelConnects"]:
            if tunnel["tunnelName"] == "server-to-client-tun1":
                return tunnel["connectToPort"]
        raise ValueError(
            "Server to Client 2 tunnel 1 connect port not found in config"
        )

    @property
    def serverToClient2Tun2ConnectPort(self) -> int:
        """Server to Client 2 tunnel 2 connect port (server-to-client-tun2 destination for client 2)"""
        for tunnel in self._client2_config["tcpTunnelConnects"]:
            if tunnel["tunnelName"] == "server-to-client-tun2":
                return tunnel["connectToPort"]
        raise ValueError(
            "Server to Client 2 tunnel 2 connect port not found in config"
        )

    @property
    def clientToServerTun1ConnectPort(self) -> int:
        """Shared backend 1 connect port (client-to-server-tun1 destination)"""
        for tunnel in self._server_config["tcpTunnelConnects"]:
            if tunnel["tunnelName"] == "client-to-server-tun1":
                return tunnel["connectToPort"]
        raise ValueError("Shared backend 1 connect port not found in config")

    @property
    def clientToServerTun2ConnectPort(self) -> int:
        """Shared backend 2 connect port (client-to-server-tun2 destination)"""
        for tunnel in self._server_config["tcpTunnelConnects"]:
            if tunnel["tunnelName"] == "client-to-server-tun2":
                return tunnel["connectToPort"]
        raise ValueError("Shared backend 2 connect port not found in config")

    @property
    def reconnectTimeoutSecs(self) -> int:
        """Reconnect timeout in seconds (standbySocketCloseDurationSecs from server config)"""
        return self._server_config.get("standbySocketCloseDurationSecs")


# Global instance for easy access
_default_port_config = None


def get_port_config() -> PortConfig:
    """Get the default port configuration instance"""
    global _default_port_config
    if _default_port_config is None:
        _default_port_config = PortConfig()
        # Log the port configuration for debugging
        logger.info(
            f"PortConfig initialized - Client1 Tun2 Port: {_default_port_config.client1ToServerTun2ListenPort}"
        )
    return _default_port_config
