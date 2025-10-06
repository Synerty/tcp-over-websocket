import logging
from pathlib import Path

from twisted.internet import defer
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks
from twisted.internet.task import deferLater
from txhttputil.site.BasicResource import BasicResource
from txhttputil.site.SiteUtil import setupSite
from txhttputil.util.PemUtil import generateDiffieHellmanParameterBytes
from vortex.VortexFactory import VortexFactory

from tcp_over_websocket.config import file_config
from tcp_over_websocket.controllers.active_remote_controller import (
    ActiveRemoteController,
)
from tcp_over_websocket.controllers.tunnel_controller import TunnelController
from tcp_over_websocket.util.vortex_util import CLIENT_VORTEX_NAME_1
from tcp_over_websocket.util.vortex_util import CLIENT_VORTEX_NAME_2
from tcp_over_websocket.util.vortex_util import SERVER_VORTEX_NAME

logger = logging.getLogger(__name__)

WEBSOCKET_URL_PATH = "vortexws"


class WebsocketServerController:
    def __init__(self, fileConfig):
        self.fileConfig = fileConfig
        self.dataExchange = fileConfig.dataExchange

        # Create active remote controller for server
        self.activeRemoteController = ActiveRemoteController(
            fileConfig.weAreServer, None
        )

        self.tunnelController = TunnelController(
            fileConfig, self.activeRemoteController
        )

        # Track online state of both clients
        self.clientOnlineState = {
            CLIENT_VORTEX_NAME_1: False,
            CLIENT_VORTEX_NAME_2: False,
        }
        self.tunnelsStarted = False
        self._failoverInProgress = False

    def start(self):
        logger.debug("Starting WebSocket server")

        platformSiteRoot = BasicResource()

        # Create websocket resources for server
        serverVortexWebsocketResource = (
            VortexFactory.createHttpWebsocketResource(SERVER_VORTEX_NAME)
        )

        # Register all websocket resources under the same path
        # The VortexFactory will route messages based on vortex names
        platformSiteRoot.putChild(
            WEBSOCKET_URL_PATH.encode(), serverVortexWebsocketResource
        )

        # Generate diffie-hellman parameter for tls v1.2 if not exists
        dhPemFile = Path(self.fileConfig.homePath()) / "dhparam.pem"
        dhPemFilePath = str(dhPemFile.absolute())

        if self.dataExchange.serverEnableSsl and not dhPemFile.exists():
            logger.info(
                "generating diffie-hellman parameter - this is one-off and "
                "may take a while"
            )
            generateDiffieHellmanParameterBytes(dhPemFilePath)

        setupSite(
            "Data Exchange",
            platformSiteRoot,
            portNum=self.dataExchange.serverPort,
            enableLogin=False,
            enableSsl=self.dataExchange.serverEnableSsl,
            sslBundleFilePath=self.dataExchange.serverTLSKeyCertCaRootBundleFilePath,
            sslEnableMutualTLS=self.dataExchange.enableMutualTLS,
            sslMutualTLSCertificateAuthorityBundleFilePath=self.dataExchange.mutualTLSTrustedCACertificateBundleFilePath,
            sslMutualTLSTrustedPeerCertificateBundleFilePath=self.dataExchange.mutualTLSTrustedPeerCertificateBundleFilePath,
            dhParamPemFilePath=dhPemFilePath,
        )

        return defer.succeed(True)

    def setup(self):
        logger.debug("Starting setup")

        activeRemoteController = self.activeRemoteController

        # Subscribe to status changes for both clients
        (
            VortexFactory.subscribeToVortexStatusChange(
                CLIENT_VORTEX_NAME_1
            ).subscribe(
                on_next=lambda nowOnline: reactor.callLater(
                    0,
                    self.handleClientStatusChange,
                    CLIENT_VORTEX_NAME_1,
                    nowOnline,
                )
            )
        )
        (
            VortexFactory.subscribeToVortexStatusChange(
                CLIENT_VORTEX_NAME_2
            ).subscribe(
                on_next=lambda nowOnline: reactor.callLater(
                    0,
                    self.handleClientStatusChange,
                    CLIENT_VORTEX_NAME_2,
                    nowOnline,
                )
            )
        )

        activeRemoteController.activeClientObservable.subscribe(
            on_next=lambda clientId: reactor.callLater(
                0, self.handleActiveClientChange, clientId
            )
        )

        # Subscribe to connection controller events
        if self.tunnelController.tunnelConnectionController:
            self.tunnelController.tunnelConnectionController.connectionObservable.subscribe(
                on_next=lambda event: reactor.callLater(
                    0,
                    lambda: logger.info(
                        f"Connection event: client {event['client_id']}, tunnel: {event['tunnel_name']}"
                    ),
                )
            )

        d = self.start()

        return d

    @inlineCallbacks
    def handleClientStatusChange(self, clientVortexName, nowOnline=False):
        logger.debug(
            f"Client {clientVortexName} status changed to: {nowOnline}"
        )

        # Update the online state for this client
        self.clientOnlineState[clientVortexName] = nowOnline

        # Update active remote controller
        if (
            self.tunnelController
            and self.tunnelController.tunnelConnectionController
        ):
            clientId = 1 if clientVortexName == CLIENT_VORTEX_NAME_1 else 2
            self.activeRemoteController.setRemoteOnline(clientId, nowOnline)

        # Count how many clients are online
        onlineClients = sum(
            1 for online in self.clientOnlineState.values() if online
        )
        logger.debug(f"Online clients count: {onlineClients}")

        # Determine what action to take
        shouldStartTunnels = onlineClients > 0 and not self.tunnelsStarted
        shouldShutdownTunnels = onlineClients == 0 and self.tunnelsStarted

        if shouldStartTunnels:
            logger.debug("Starting tunnels - first client connected")
            self.tunnelsStarted = True
            yield self.tunnelController.startTunnels()
        elif shouldShutdownTunnels:
            logger.debug("Shutting down tunnels - last client disconnected")
            self.tunnelsStarted = False
            yield self.tunnelController.stopTunnels()
        else:
            logger.debug("No tunnel state change needed")
            return

    # Subscribe to active remote controller observables
    @inlineCallbacks
    def handleActiveClientChange(self, clientId):
        logger.info(f"Active client changed to: {clientId}")
        # When active client changes, trigger failover process
        if clientId is None:
            logger.info("No active client available")
            return

        # Check if we're already in a failover process
        if self._failoverInProgress:
            logger.info(
                f"Failover already in progress, ignoring active client change to {clientId}"
            )
            return

        self._failoverInProgress = True
        try:
            fileConfig = file_config.FileConfig()
            closeDuration = fileConfig.standbySocketCloseDurationSecs

            logger.info(
                f"Server starting failover coordination: closing listen tunnels"
                f" for {closeDuration} seconds due to active client change"
                f" to {clientId}"
            )

            # Stop listen tunnels to prevent new connections during failover
            yield self.tunnelController.stopListenTunnels()
            logger.info(
                f"Server listen tunnels stopped for failover coordination"
            )

            # Wait for the configured duration to allow clients to complete their failover
            yield deferLater(reactor, closeDuration, lambda: None)
            logger.info(
                f"Server failover wait period completed ({closeDuration}s)"
            )

            # Check if the active client is still the same after our wait
            currentActiveClient = (
                self.activeRemoteController.getActiveClientId()
            )
            if currentActiveClient == clientId:
                logger.info(
                    f"Restarting server listen tunnels - active client confirmed as {clientId}"
                )
                yield self.tunnelController.startListenTunnels()
                logger.info(
                    f"Server listen tunnels restarted for active client {clientId}"
                )
            else:
                logger.warning(
                    f"Active client changed during failover coordination: "
                    f"expected {clientId}, now {currentActiveClient}. "
                    f"Listen tunnels will restart when client state stabilizes."
                )
                if currentActiveClient is not None:
                    # Another client became active, restart tunnels for the new active client
                    yield self.tunnelController.startListenTunnels()
                    logger.info(
                        f"Server listen tunnels restarted for new active client {currentActiveClient}"
                    )
        finally:
            self._failoverInProgress = False
