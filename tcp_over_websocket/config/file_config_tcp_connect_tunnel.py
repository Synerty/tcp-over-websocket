from jsoncfg.functions import ConfigWithWrapper


class FileConfigTcpConnectTunnel:
    def __init__(self, cfg: ConfigWithWrapper, node):
        self._cfg = cfg
        self._node = node

    @property
    def tunnelName(self) -> str:
        return self._node["tunnelName"]

    @property
    def connectToPort(self) -> int:
        return self._node["connectToPort"]

    @property
    def connectToHost(self) -> str:
        return self._node["connectToHost"]
