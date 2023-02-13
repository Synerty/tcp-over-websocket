import os
from typing import Optional
from urllib.parse import urlparse

from jsoncfg.functions import ConfigWithWrapper
from jsoncfg.value_mappers import require_bool
from jsoncfg.value_mappers import require_string


class FileConfigDataExchange:
    def __init__(self, cfg: ConfigWithWrapper):
        self._cfg = cfg

    @property
    def serverEnableSsl(self) -> bool:
        return "https" in self.serverUrl.lower()

    @property
    def serverPort(self) -> int:
        parseResult = urlparse(self.serverUrl)
        return parseResult.port

    @property
    def serverHost(self) -> str:
        parseResult = urlparse(self.serverUrl)
        return parseResult.hostname

    @property
    def serverUrl(self) -> str:
        with self._cfg as c:
            return c.dataExchange.serverUrl(
                "http://server:8080", require_string
            )

    @property
    def serverTLSKeyCertCaRootBundleFilePath(self) -> Optional[str]:
        default = (
            "/path/to/key-cert-ca-root-chain.pem or "
            "c:\\path\\to\\key-cert-ca-root-chain.pem"
        )
        with self._cfg as c:
            file = c.dataExchange.tlsBundleFilePath(default, require_string)
            if os.path.exists(file):
                return file
            return None

    @property
    def enableMutualTLS(self) -> Optional[bool]:
        with self._cfg as c:
            return c.dataExchange.enableMutualTLS(False, require_bool)

    @property
    def mutualTLSTrustedCACertificateBundleFilePath(self) -> Optional[str]:
        default = "/path/to/trusted-ca.pem or c:\\path\\to\\trusted-ca.pem"
        with self._cfg as c:
            file = c.dataExchange.mutualTLSTrustedCACertificateBundleFilePath(
                default, require_string
            )
            if os.path.exists(file):
                return file
            return None

    @property
    def mutualTLSTrustedPeerCertificateBundleFilePath(
        self,
    ) -> Optional[str]:
        default = (
            "/path/to/certs-of-peers.pem or c:\\path\\to\\certs-of-peers.pem"
        )
        with self._cfg as c:
            file = c.dataExchange.mutualTLSTrustedPeerCertificateBundleFilePath(
                default, require_string
            )
            if os.path.exists(file):
                return file
            return None