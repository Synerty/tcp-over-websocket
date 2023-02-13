import logging
import os
from abc import ABCMeta

from jsoncfg.functions import ConfigWithWrapper
from jsoncfg.functions import save_config

logger = logging.getLogger(__name__)


class FileConfigABC(metaclass=ABCMeta):
    """
    This class creates a basic configuration
    """

    DEFAULT_FILE_CHMOD = 0o600
    DEFAULT_DIR_CHMOD = 0o700

    __instance = None

    def __new__(cls):
        if cls.__instance is not None:
            return cls.__instance

        self = super(FileConfigABC, cls).__new__(cls)
        cls.__instance = self
        return self

    def __init__(self):
        self._homePath = os.path.expanduser("~/tcp-over-websocket.home")

        if not os.path.isdir(self._homePath):
            assert not os.path.exists(self._homePath)
            os.makedirs(self._homePath, self.DEFAULT_DIR_CHMOD)

        self._configFilePath = os.path.join(self._homePath, "config.json")

        if not os.path.isfile(self._configFilePath):
            assert not os.path.exists(self._configFilePath)
            with open(self._configFilePath, "w") as fobj:
                fobj.write("{}")

        self._cfg = ConfigWithWrapper(self._configFilePath)

        self._homePathAlias = "%(" + self._homePath + ")s"

    def _save(self):
        save_config(self._configFilePath, self._cfg)

    def _chkDir(self, path):
        if not os.path.isdir(path):
            assert not os.path.exists(path)
            os.makedirs(path, self.DEFAULT_DIR_CHMOD)
        return path

    @property
    def homePath(self) -> str:
        return self._homePath
