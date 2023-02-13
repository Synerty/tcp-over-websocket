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
    @property
    def weAreServer(self) -> bool:
        with self._cfg as c:
            return c.weAreServer(False, require_bool)

    @property
    def tcpTunnelListens(self) -> list:
        with self._cfg as c:
            return [
                FileConfigTcpListenTunnel(self._cfg, node)
                for node in c.tcpTunnelListens([], require_array)
            ]

    @property
    def tcpTunnelConnects(self) -> list:
        with self._cfg as c:
            return [
                FileConfigTcpConnectTunnel(self._cfg, node)
                for node in c.tcpTunnelConnects([], require_array)
            ]

    @property
    def dataExchange(self) -> FileConfigDataExchange:
        return FileConfigDataExchange(self._cfg)

    @property
    def logging(self) -> FileConfigLogging:
        return FileConfigLogging(self._cfg)
