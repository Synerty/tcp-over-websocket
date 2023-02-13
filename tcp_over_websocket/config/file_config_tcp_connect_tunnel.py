from jsoncfg.functions import ConfigWithWrapper
from jsoncfg.value_mappers import require_integer
from jsoncfg.value_mappers import require_string


class FileConfigTcpConnectTunnel:
    def __init__(self, cfg: ConfigWithWrapper, node):
        self._cfg = cfg
        self._node = node

    @property
    def tunnelName(self) -> str:
        with self._cfg:
            return self._node.tunnelName("unique tunnel name", require_string)

    @property
    def connectToPort(self) -> int:
        with self._cfg:
            return self._node.connectToPort(False, require_integer)

    @property
    def connectToHost(self) -> str:
        with self._cfg:
            return self._node.connectToHost(False, require_string)
