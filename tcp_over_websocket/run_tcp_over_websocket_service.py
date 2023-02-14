import sys
from pathlib import Path

from twisted.internet.defer import Deferred
from twisted.internet.defer import inlineCallbacks
from txhttputil.site.BasicResource import BasicResource
from txhttputil.site.SiteUtil import setupSite
from txhttputil.util.PemUtil import generateDiffieHellmanParameterBytes
from vortex.DeferUtil import vortexLogFailure
from vortex.VortexFactory import VortexFactory

from tcp_over_websocket.tcp_tunnel.tcp_tunnel_connect import TcpTunnelConnect
from tcp_over_websocket.tcp_tunnel.tcp_tunnel_listen import TcpTunnelListen
from tcp_over_websocket.util.log_util import setupLogger
from tcp_over_websocket.util.vortex_util import CLIENT_VORTEX_NAME
from tcp_over_websocket.util.vortex_util import SERVER_VORTEX_NAME
from tcp_over_websocket.config import file_config

# Setup the logger to catch the startup.
setupLogger()

from twisted.internet import reactor, defer

import logging


logger = logging.getLogger(__name__)

WEBSOCKET_URL_PATH = "vortexws"


def serveVortexServer():
    logger.debug("Starting serveVortexServer")
    fileConfig = file_config.FileConfig()

    platformSiteRoot = BasicResource()

    vortexWebsocketResource = VortexFactory.createHttpWebsocketResource(
        SERVER_VORTEX_NAME
    )
    platformSiteRoot.putChild(
        WEBSOCKET_URL_PATH.encode(), vortexWebsocketResource
    )

    dataExchange = fileConfig.dataExchange

    # generate diffie-hellman parameter for tls v1.2 if not exists
    dhPemFile = Path(fileConfig.homePath()) / "dhparam.pem"
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
        portNum=dataExchange.serverPort,
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
    logger.debug("Starting connectVortexClient")
    fileConfig = file_config.FileConfig()
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
    logger.debug("Starting setupLogging")
    fileConfig = file_config.FileConfig()
    # Set default logging level
    logging.root.setLevel(fileConfig.logging.loggingLevel)

    from tcp_over_websocket.util.log_util import updateLoggerHandlers

    logFileName = str(Path(fileConfig.homePath()) / "tcp_over_websocket.log")

    updateLoggerHandlers(
        fileConfig.logging.daysToKeep,
        fileConfig.logging.logToStdout,
        logFileName,
    )

    if fileConfig.logging.loggingLogToSyslogHost:
        from tcp_over_websocket.util.log_util import setupLoggingToSyslogServer

        setupLoggingToSyslogServer(
            fileConfig.logging.loggingLogToSyslogHost,
            fileConfig.logging.loggingLogToSyslogPort,
            fileConfig.logging.loggingLogToSyslogFacility,
        )

    # Enable deferred debugging if DEBUG is on.
    if logging.root.level == logging.DEBUG:
        defer.setDebugging(True)


def createTunnels(fileConfig):
    logger.debug("Starting createTunnels")
    otherVortexName = (
        CLIENT_VORTEX_NAME if fileConfig.weAreServer else SERVER_VORTEX_NAME
    )
    tunnelHandlers = []
    tunnelHandlers.extend(
        [
            TcpTunnelListen(listenCfg, otherVortexName)
            for listenCfg in fileConfig.tcpTunnelListens
        ]
    )
    tunnelHandlers.extend(
        [
            TcpTunnelConnect(connectCfg, otherVortexName)
            for connectCfg in fileConfig.tcpTunnelConnects
        ]
    )

    @inlineCallbacks
    def startTunnelsCallable(*args):
        for tunnelHandler in tunnelHandlers:
            yield tunnelHandler.start()

    @inlineCallbacks
    def shutdownTunnelsCallable(*args):
        for tunnelHandler in tunnelHandlers:
            yield tunnelHandler.shutdown()

    return startTunnelsCallable, shutdownTunnelsCallable


def setupForClient(startTunnelsCallable, shutdownTunnelsCallable):
    logger.debug("Starting setupForClient")
    # Make sure we restart if the vortex goes offline

    class _State:
        restartEnabled = True

    def restart(*args):
        if not _State.restartEnabled:
            return

        from tcp_over_websocket.util.restart_util import RestartUtil

        RestartUtil.restartProcess()

    (
        VortexFactory.subscribeToVortexStatusChange(SERVER_VORTEX_NAME)
        .filter(lambda online: online is False)
        .subscribe(on_next=restart)
    )

    @inlineCallbacks
    def shutdown(*args):
        _State.restartEnabled = False
        yield shutdownTunnelsCallable()

    reactor.addSystemEventTrigger("before", "shutdown", shutdown)

    d = connectVortexClient()
    d.addCallback(startTunnelsCallable)

    # If we have errors, restart
    d.addErrback(restart)

    return d


def setupForServer(startTunnelsCallable, shutdownTunnelsCallable):
    logger.debug("Starting setupForServer")
    # Make sure we restart if the vortex goes offline
    def clientVortexOnline(*args):
        reactor.callFromThread(startTunnelsCallable)

    # Make sure we restart if the vortex goes offline
    def clientVortexOffline(*args):
        reactor.callFromThread(shutdownTunnelsCallable)

    (
        VortexFactory.subscribeToVortexStatusChange(
            CLIENT_VORTEX_NAME
        ).subscribe(
            on_next=(
                lambda online: clientVortexOnline()
                if online
                else clientVortexOffline()
            )
        )
    )

    d = serveVortexServer()

    return d


def main():
    logger.debug("Starting main")
    fileConfig = file_config.FileConfig()
    # defer.setDebugging(True)
    # sys.argv.remove(DEBUG_ARG)
    # import pydevd
    # pydevd.settrace(suspend=False)

    setupLogging()

    startTunnelsCallable, shutdownTunnelsCallable = createTunnels(fileConfig)

    # Load all Plugins
    if fileConfig.weAreServer:
        d = setupForServer(startTunnelsCallable, shutdownTunnelsCallable)
    else:
        d = setupForClient(startTunnelsCallable, shutdownTunnelsCallable)

    def startedSuccessfully(_):
        import tcp_over_websocket

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

    main()
