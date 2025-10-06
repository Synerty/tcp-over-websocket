import logging
import sys
from pathlib import Path

from twisted.internet import reactor, defer
from vortex.DeferUtil import vortexLogFailure

from tcp_over_websocket.config import file_config
from tcp_over_websocket.controllers.websocket_client_controller import (
    WebsocketClientController,
)
from tcp_over_websocket.controllers.websocket_server_controller import (
    WebsocketServerController,
)
from tcp_over_websocket.util.log_util import (
    setupLogger,
    updateLoggerHandlers,
    setupLoggingToSyslogServer,
)
import tcp_over_websocket

# Setup the logger to catch the startup.
setupLogger()


logger = logging.getLogger(__name__)


def setupLogging():
    logger.debug("Starting setupLogging")
    fileConfig = file_config.FileConfig()
    # Set default logging level
    logging.root.setLevel(fileConfig.logging.loggingLevel)

    logFileName = str(Path(fileConfig.homePath()) / "tcp_over_websocket.log")

    updateLoggerHandlers(
        fileConfig.logging.daysToKeep,
        fileConfig.logging.logToStdout,
        logFileName,
    )

    if fileConfig.logging.loggingLogToSyslogHost:
        setupLoggingToSyslogServer(
            fileConfig.logging.loggingLogToSyslogHost,
            fileConfig.logging.loggingLogToSyslogPort,
            fileConfig.logging.loggingLogToSyslogFacility,
        )

    # Enable deferred debugging if DEBUG is on.
    if logging.root.level == logging.DEBUG:
        defer.setDebugging(True)


def main():
    logger.debug("Starting main")
    fileConfig = file_config.FileConfig()
    # defer.setDebugging(True)
    # sys.argv.remove(DEBUG_ARG)
    # import pydevd
    # pydevd.settrace(suspend=False)

    # Load all Plugins
    if fileConfig.weAreServer:
        websocketServerController = WebsocketServerController(fileConfig)
        d = websocketServerController.setup()
    else:
        websocketClientController = WebsocketClientController(fileConfig)
        d = websocketClientController.setup()

    def startedSuccessfully(_):
        logger.info(
            "TCP over Websocket running, version=%s",
            tcp_over_websocket.__version__,
        )
        return _

    d.addCallback(startedSuccessfully)
    d.addErrback(vortexLogFailure, logger, consumeError=False)

    reactor.run()


if __name__ == "__main__":
    if len(sys.argv) == 2:
        assert Path(sys.argv[1]).is_dir(), "Passed argument is not a directory"

        file_config.FileConfig.setHomePath(sys.argv[1])

    setupLogging()
    main()
