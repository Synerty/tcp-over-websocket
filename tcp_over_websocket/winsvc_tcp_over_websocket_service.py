import logging

import win32service
import win32serviceutil
from twisted.internet import reactor

import tcp_over_websocket
from tcp_over_websocket.util.restart_util import IS_WIN_SVC

logger = logging.getLogger(__name__)


class _Service(win32serviceutil.ServiceFramework):
    _svc_name_ = "tcp-over-websocket"
    _svc_display_name_ = "TCP over Websocket " + tcp_over_websocket.__version__
    _exe_args_ = IS_WIN_SVC
    _svc_deps_ = ["RpcSs"]

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)

        reactor.addSystemEventTrigger("after", "shutdown", self._notifyOfStop)

    def _notifyOfStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOPPED)

    def _notifyOfStart(self):
        self.ReportServiceStatus(win32service.SERVICE_RUNNING)

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        reactor.callFromThread(reactor.stop)

    def SvcDoRun(self):
        self.ReportServiceStatus(win32service.SERVICE_START_PENDING)
        try:

            reactor.callLater(1, self._notifyOfStart)

            from tcp_over_websocket import run_tcp_over_websocket_service

            run_tcp_over_websocket_service.main()

        except Exception as e:
            logger.exception(e)
            raise


def main():
    win32serviceutil.HandleCommandLine(_Service)


if __name__ == "__main__":
    main()
