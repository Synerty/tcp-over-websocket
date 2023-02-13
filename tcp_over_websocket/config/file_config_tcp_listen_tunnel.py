from jsoncfg.functions import ConfigWithWrapper
from jsoncfg.value_mappers import require_integer
from jsoncfg.value_mappers import require_string


class FileConfigTcpListenTunnel:
    def __init__(self, cfg: ConfigWithWrapper, node):
        self._cfg = cfg
        self._node = node

    @property
    def tunnelName(self) -> str:
        with self._cfg:
            return self._node.tunnelName("unique tunnel name", require_string)

    @property
    def listenPort(self) -> int:
        with self._cfg:
            return self._node.listenPort(30102, require_integer)

    @property
    def listenBindAddress(self) -> str:
        with self._cfg:
            return self._node.listenBindAddress("127.0.0.1", require_string)
