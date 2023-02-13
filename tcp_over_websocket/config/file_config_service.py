import logging
from typing import Optional

from jsoncfg.functions import ConfigWithWrapper
from jsoncfg.value_mappers import require_bool
from jsoncfg.value_mappers import require_integer
from jsoncfg.value_mappers import require_string

logger = logging.getLogger(__name__)


class FileConfigLogging:
    def __init__(self, cfg: ConfigWithWrapper):
        self._cfg = cfg

    @property
    def loggingLevel(self) -> str:
        with self._cfg as c:
            lvl = c.logging.level("INFO", require_string)
            if lvl in logging._nameToLevel:
                return lvl

            logger.warning(
                "Logging level %s is not valid, defauling to INFO", lvl
            )
            return "INFO"

    @property
    def logToStdout(self) -> bool:
        with self._cfg as c:
            return c.logging.logToStdout(False, require_bool)

    @property
    def daysToKeep(self) -> int:
        with self._cfg as c:
            val = c.logging.daysToKeep(14, require_integer)

            # As of v3.1+ cleanup the old log file properties
            for prop in ("rotateSizeMb", "rotationsToKeep"):
                if prop in c.logging:
                    logging = {}
                    logging.update(iter(c.logging))
                    del logging[prop]
                    c.logging = logging

            return val

    @property
    def loggingLogToSyslogHost(self) -> Optional[str]:
        with self._cfg as c:
            return c.logging.syslog.logToSysloyHost(None)

    @property
    def loggingLogToSyslogPort(self) -> int:
        with self._cfg as c:
            return c.logging.syslog.logToSysloyPort(514, require_integer)

    @property
    def loggingLogToSyslogFacility(self) -> str:
        with self._cfg as c:
            return c.logging.syslog.logToSysloyProtocol("user", require_string)
