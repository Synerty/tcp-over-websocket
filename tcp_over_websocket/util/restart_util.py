import logging
import os
import sys

from twisted.internet import reactor

from tcp_over_websocket.util.windows_util import isWindows

logger = logging.getLogger(__name__)

IS_WIN_SVC = "isWinSvc"


class RestartUtil:
    @classmethod
    def _restartProcessWinSvc(cls) -> None:
        reactor.callFromThread(reactor.stop)

    @classmethod
    def _restartProcessNormal(cls) -> None:
        """Restart Process

        Restarts the current program.

        Note: this function does not return.
        Any cleanup action (like saving data) must be done before calling this function.

        Note: When peek is started by a windows service, this method is replaced with
        one that just restarts the windows service.

        """

        if IS_WIN_SVC in sys.argv:
            reactor.callFromThread(reactor.stop)
            return

        python = sys.executable
        argv = list(sys.argv)

        def addExe(val):
            if "run_tcp_" not in val:
                return val

            if isWindows and not val.lower().endswith(".exe"):
                return val + ".exe"

            return val

        argv = map(addExe, argv)
        os.execl(python, python, *argv)

    restartProcess = (
        _restartProcessWinSvc
        if IS_WIN_SVC in sys.argv
        else _restartProcessNormal
    )
