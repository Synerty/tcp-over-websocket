import logging

from twisted.internet import reactor
from twisted.internet.defer import Deferred
from twisted.internet.defer import inlineCallbacks
from twisted.internet.task import deferLater
from twisted.python.failure import Failure
from vortex.DeferUtil import vortexLogFailure
from vortex.VortexFactory import VortexFactory

from tcp_over_websocket.controllers.active_remote_controller import (
    ActiveRemoteController,
)
from tcp_over_websocket.controllers.tunnel_controller import TunnelController
from tcp_over_websocket.util.restart_util import RestartUtil
from tcp_over_websocket.util.vortex_util import CLIENT_VORTEX_NAME_1
from tcp_over_websocket.util.vortex_util import CLIENT_VORTEX_NAME_2
from tcp_over_websocket.util.vortex_util import SERVER_VORTEX_NAME

logger = logging.getLogger(__name__)

WEBSOCKET_URL_PATH = "vortexws"


class WebsocketClientController:
    def __init__(self, fileConfig):
        self.fileConfig = fileConfig
        self.dataExchangeCfg = fileConfig.dataExchange

        # Create active remote controller for client
        self.activeRemoteController = ActiveRemoteController(
            fileConfig.weAreServer, fileConfig.clientId
        )

        self.tunnelController = TunnelController(
            fileConfig, self.activeRemoteController
        )

    def connect(self) -> Deferred:
        logger.debug("Starting WebSocket client connection")

        scheme = "wss" if self.dataExchangeCfg.serverEnableSsl else "ws"
        host = self.dataExchangeCfg.serverHost
        port = self.dataExchangeCfg.serverPort

        # Use client-specific vortex name
        clientVortexName = (
            CLIENT_VORTEX_NAME_1
            if self.fileConfig.clientId == 1
            else CLIENT_VORTEX_NAME_2
        )

        return VortexFactory.createWebsocketClient(
            clientVortexName,
            host,
            port,
            url=f"{scheme}://{host}:{port}/{WEBSOCKET_URL_PATH}",
            sslEnableMutualTLS=self.dataExchangeCfg.enableMutualTLS,
            sslClientCertificateBundleFilePath=self.dataExchangeCfg.serverTLSKeyCertCaRootBundleFilePath,
            sslMutualTLSCertificateAuthorityBundleFilePath=self.dataExchangeCfg.mutualTLSTrustedCACertificateBundleFilePath,
            sslMutualTLSTrustedPeerCertificateBundleFilePath=self.dataExchangeCfg.mutualTLSTrustedPeerCertificateBundleFilePath,
        )

    @inlineCallbacks
    def _handleUpDownTunnels(self, nowOnline=False):
        # Update server online status in active remote controller
        self.activeRemoteController.setRemoteOnline(0, nowOnline)
        if nowOnline:
            yield self.tunnelController.startTunnels()
        else:
            yield self.tunnelController.stopTunnels()

    def _restart(self, failure: Failure):
        vortexLogFailure(failure, logger)
        logger.error("Restarting because of error")
        RestartUtil.restartProcess()

    def setup(self):
        logger.debug("Starting setup")

        # Subscribe to active remote controller observables
        self.activeRemoteController.serverOnlineObservable.subscribe(
            on_next=lambda online: reactor.callLater(
                0,
                lambda: logger.info(f"Server online status changed: {online}"),
            )
        )

        # Subscribe to standby transition events
        self.activeRemoteController.standbyTransitionObservable.subscribe(
            on_next=lambda event: reactor.callLater(
                0, self._handleStandbyTransition, event
            )
        )

        # Subscribe to connection controller events
        if self.tunnelController.tunnelConnectionController:
            self.tunnelController.tunnelConnectionController.connectionObservable.subscribe(
                on_next=lambda event: reactor.callLater(
                    0, lambda: logger.info(f"Connection event: {event}")
                )
            )

        (
            VortexFactory.subscribeToVortexStatusChange(
                SERVER_VORTEX_NAME
            ).subscribe(
                on_next=lambda nowOnline: reactor.callLater(
                    0, self._handleUpDownTunnels, nowOnline
                )
            )
        )

        reactor.addSystemEventTrigger(
            "before",
            "shutdown",
            lambda: reactor.callLater(0, self.tunnelController.stopTunnels),
        )

        d = self.connect()

        # If we have errors, restart
        d.addErrback(self._restart)

        return d

    @inlineCallbacks
    def _handleStandbyTransition(self, transitionEvent):
        """Handle standby transition event from observable"""
        activeClientId = transitionEvent.get("active_client_id")
        transitionType = transitionEvent.get("transition_type")

        logger.info(
            f"Received standby transition event: {transitionType}, active client: {activeClientId}"
        )

        closeDuration = self.fileConfig.standbySocketCloseDurationSecs

        logger.info(
            f"Client (ID: {self.fileConfig.clientId}) starting failover wait:"
            f" became standby,"
            f" closing listen ports for {closeDuration}"
            f" seconds due to client {activeClientId} becoming active"
        )

        # Stop only listen tunnels (this closes the listening ports but keeps connect tunnels open)
        yield self.tunnelController.stopListenTunnels()

        # Wait for the configured duration
        yield deferLater(reactor, closeDuration, lambda: None)

        # Check if server is still online before restarting listen tunnels
        if self.activeRemoteController.isServerOnline():
            logger.info(
                "Failover wait completed: server online,"
                " reopening listen ports after standby period"
            )
            yield self.tunnelController.startListenTunnels()
        else:
            logger.info(
                "Failover wait completed: server offline,"
                " listen ports will reopen when server comes back online"
            )
