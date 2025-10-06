import logging

from twisted.internet.defer import inlineCallbacks

from tcp_over_websocket.controllers.tunnel_connection_controller import (
    TunnelConnectionController,
)
from tcp_over_websocket.tcp_tunnel.tcp_tunnel_connect import TcpTunnelConnect
from tcp_over_websocket.tcp_tunnel.tcp_tunnel_listen import TcpTunnelListen

logger = logging.getLogger(__name__)


class TunnelController:
    def __init__(self, fileConfig, activeRemoteController):
        logger.debug("Starting TunnelController initialization")

        self.fileConfig = fileConfig
        self.activeRemoteController = activeRemoteController

        # Always pass activeRemoteController to TunnelConnectionController
        self.tunnelConnectionController = TunnelConnectionController(
            self.activeRemoteController
        )

        self.tunnelHandlers = []
        self.tunnelHandlers.extend(
            [
                TcpTunnelListen(
                    listenCfg,
                    self.activeRemoteController,
                    self.tunnelConnectionController,
                )
                for listenCfg in fileConfig.tcpTunnelListens
            ]
        )
        self.tunnelHandlers.extend(
            [
                TcpTunnelConnect(connectCfg, self.activeRemoteController)
                for connectCfg in fileConfig.tcpTunnelConnects
            ]
        )

    @inlineCallbacks
    def startTunnels(self):
        logger.info(f"Starting {len(self.tunnelHandlers)} tunnel handlers")
        self.activeRemoteController.start()
        if self.tunnelConnectionController:
            self.tunnelConnectionController.start(self.fileConfig.weAreServer)
        for i, tunnelHandler in enumerate(self.tunnelHandlers):
            logger.info(
                f"Starting tunnel handler {i + 1}/{len(self.tunnelHandlers)}: {type(tunnelHandler).__name__}"
            )
            yield tunnelHandler.start()
            logger.info(
                f"Started tunnel handler {i + 1}/{len(self.tunnelHandlers)}: {type(tunnelHandler).__name__}"
            )
        logger.info("All tunnel handlers started successfully")

    @inlineCallbacks
    def startListenTunnels(self):
        """Start only the listen tunnel handlers"""
        listenHandlers = [h for h in self.tunnelHandlers if h.side == 'listen']
        logger.info(f"Starting {len(listenHandlers)} listen tunnel handlers")
        for i, tunnelHandler in enumerate(listenHandlers):
            logger.info(
                f"Starting listen tunnel handler {i + 1}/{len(listenHandlers)}: {type(tunnelHandler).__name__}"
            )
            yield tunnelHandler.start()
            logger.info(
                f"Started listen tunnel handler {i + 1}/{len(listenHandlers)}: {type(tunnelHandler).__name__}"
            )
        logger.info("All listen tunnel handlers started successfully")

    @inlineCallbacks
    def startConnectTunnels(self):
        """Start only the connect tunnel handlers"""
        connectHandlers = [h for h in self.tunnelHandlers if h.side == 'connect']
        logger.info(f"Starting {len(connectHandlers)} connect tunnel handlers")
        for i, tunnelHandler in enumerate(connectHandlers):
            logger.info(
                f"Starting connect tunnel handler {i + 1}/{len(connectHandlers)}: {type(tunnelHandler).__name__}"
            )
            yield tunnelHandler.start()
            logger.info(
                f"Started connect tunnel handler {i + 1}/{len(connectHandlers)}: {type(tunnelHandler).__name__}"
            )
        logger.info("All connect tunnel handlers started successfully")

    @inlineCallbacks
    def stopTunnels(self):
        for tunnelHandler in self.tunnelHandlers:
            yield tunnelHandler.shutdown()
        if self.tunnelConnectionController:
            self.tunnelConnectionController.shutdown()
        self.activeRemoteController.shutdown()

    @inlineCallbacks
    def stopListenTunnels(self):
        """Stop only the listen tunnel handlers"""
        listenHandlers = [h for h in self.tunnelHandlers if h.side == 'listen']
        logger.info(f"Stopping {len(listenHandlers)} listen tunnel handlers")
        for tunnelHandler in listenHandlers:
            yield tunnelHandler.shutdown()
        logger.info("All listen tunnel handlers stopped")

    @inlineCallbacks
    def stopConnectTunnels(self):
        """Stop only the connect tunnel handlers"""
        connectHandlers = [h for h in self.tunnelHandlers if h.side == 'connect']
        logger.info(f"Stopping {len(connectHandlers)} connect tunnel handlers")
        for tunnelHandler in connectHandlers:
            yield tunnelHandler.shutdown()
        logger.info("All connect tunnel handlers stopped")
