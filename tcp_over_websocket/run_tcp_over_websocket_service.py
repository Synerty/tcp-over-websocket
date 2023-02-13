from pathlib import Path

from twisted.internet.defer import Deferred
from txhttputil.site.BasicResource import BasicResource
from txhttputil.site.SiteUtil import setupSite
from txhttputil.util.PemUtil import generateDiffieHellmanParameterBytes
from vortex.DeferUtil import vortexLogFailure
from vortex.VortexFactory import VortexFactory

from tcp_over_websocket.config.file_config import fileConfig
from tcp_over_websocket.tcp_tunnel.tcp_tunnel_connect import TcpTunnelConnect
from tcp_over_websocket.tcp_tunnel.tcp_tunnel_listen import TcpTunnelListen
from tcp_over_websocket.util.log_util import setupLogger
from tcp_over_websocket.util.vortex_util import CLIENT_VORTEX_NAME
from tcp_over_websocket.util.vortex_util import SERVER_VORTEX_NAME

# Setup the logger to catch the startup.
setupLogger()

from twisted.internet import reactor, defer

import logging


logger = logging.getLogger(__name__)

WEBSOCKET_URL_PATH = "vortexws"


def serveVortexServer():

    platformSiteRoot = BasicResource()

    vortexWebsocketResource = VortexFactory.createHttpWebsocketResource(
        SERVER_VORTEX_NAME
    )
    platformSiteRoot.putChild(
        WEBSOCKET_URL_PATH.encode(), vortexWebsocketResource
    )

    dataExchange = fileConfig.dataExchange

    # generate diffie-hellman parameter for tls v1.2 if not exists
    dhPemFile = Path(fileConfig.homePath) / "dhparam.pem"
    dhPemFilePath = str(dhPemFile.absolute())

    if dataExchange.serverEnableSsl and not dhPemFile.exists():
        logger.info(
            "generating diffie-hellman parameter - this is one-off and "
            "may take a while"
        )
        generateDiffieHellmanParameterBytes(dhPemFilePath)

    setupSite(
        "Data Exchange",
        platformSiteRoot,
        portNum=dataExchange.sitePort,
        enableLogin=False,
        enableSsl=dataExchange.serverEnableSsl,
        sslBundleFilePath=dataExchange.serverTLSKeyCertCaRootBundleFilePath,
        sslEnableMutualTLS=dataExchange.enableMutualTLS,
        sslMutualTLSCertificateAuthorityBundleFilePath=dataExchange.mutualTLSTrustedCACertificateBundleFilePath,
        sslMutualTLSTrustedPeerCertificateBundleFilePath=dataExchange.mutualTLSTrustedPeerCertificateBundleFilePath,
        dhParamPemFilePath=dhPemFilePath,
    )

    return defer.succeed(True)


def connectVortexClient() -> Deferred:
    dataExchangeCfg = fileConfig.dataExchange

    scheme = "wss" if dataExchangeCfg.serverEnableSsl else "ws"
    host = dataExchangeCfg.serverHost
    port = dataExchangeCfg.serverPort

    return VortexFactory.createWebsocketClient(
        CLIENT_VORTEX_NAME,
        host,
        port,
        url=f"{scheme}://{host}:{port}/{WEBSOCKET_URL_PATH}",
        sslEnableMutualTLS=dataExchangeCfg.enableMutualTLS,
        sslClientCertificateBundleFilePath=dataExchangeCfg.serverTLSKeyCertCaRootBundleFilePath,
        sslMutualTLSCertificateAuthorityBundleFilePath=dataExchangeCfg.mutualTLSTrustedCACertificateBundleFilePath,
        sslMutualTLSTrustedPeerCertificateBundleFilePath=dataExchangeCfg.mutualTLSTrustedPeerCertificateBundleFilePath,
    )


def setupLogging():
    # Set default logging level
    logging.root.setLevel(fileConfig.loggingLevel)

    from tcp_over_websocket.util.log_util import updateLoggerHandlers

    updateLoggerHandlers(
        fileConfig.daysToKeep,
        fileConfig.logToStdout,
    )

    if fileConfig.loggingLogToSyslogHost:
        from tcp_over_websocket.util.log_util import setupLoggingToSyslogServer

        setupLoggingToSyslogServer(
            fileConfig.loggingLogToSyslogHost,
            fileConfig.loggingLogToSyslogPort,
            fileConfig.loggingLogToSyslogFacility,
        )

    # Enable deferred debugging if DEBUG is on.
    if logging.root.level == logging.DEBUG:
        defer.setDebugging(True)


def main():
    # defer.setDebugging(True)
    # sys.argv.remove(DEBUG_ARG)
    # import pydevd
    # pydevd.settrace(suspend=False)

    # Make sure we restart if the vortex goes offline
    def restart(_=None):
        from tcp_over_websocket.util.restart_util import RestartUtil

        RestartUtil.restartProcess()

    (
        VortexFactory.subscribeToVortexStatusChange("other_vortex")
        .filter(lambda online: online is False)
        .subscribe(on_next=restart)
    )

    otherVortexName = (
        SERVER_VORTEX_NAME if fileConfig.weAreServer else CLIENT_VORTEX_NAME
    )
    tcpHandlers = []
    tcpHandlers.extend(
        [
            TcpTunnelListen(listenCfg, otherVortexName)
            for listenCfg in fileConfig.tcpTunnelListens
        ]
    )
    tcpHandlers.extend(
        [
            TcpTunnelConnect(connectCfg, otherVortexName)
            for connectCfg in fileConfig.tcpTunnelConnects
        ]
    )

    # Load all Plugins
    if fileConfig.weAreServer:
        d = serveVortexServer()
    else:
        d = connectVortexClient()

    def startTunnels(_):
        for tcpHandler in tcpHandlers:
            tcpHandler.start()

    def startedSuccessfully(_):
        import tcp_over_websocket

        logger.info(
            "TCP over Websocket running, version=%s",
            tcp_over_websocket.__version__,
        )
        return _

    d.addErrback(vortexLogFailure, logger, consumeError=False)
    d.addErrback(lambda _: restart())
    d.addCallback(startTunnels)
    d.addCallback(startedSuccessfully)

    def shutdownTunnels(_):
        for tcpHandler in tcpHandlers:
            tcpHandler.shutdown()

    reactor.addSystemEventTrigger("before", "shutdown", shutdownTunnels)

    reactor.run()


if __name__ == "__main__":
    main()
