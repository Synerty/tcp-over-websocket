#!/usr/bin/env python3

import logging
import sys
from pathlib import Path


# Add the parent directory to Python path so we can import tcp_over_websocket
sys.path.insert(0, str(Path(__file__).parent.parent))

from tcp_over_websocket.config import file_config
from tcp_over_websocket.config.file_config_data_exchange import (
    FileConfigDataExchange,
)
from tcp_over_websocket.config.file_config_tcp_connect_tunnel import (
    FileConfigTcpConnectTunnel,
)
from tcp_over_websocket.run_tcp_over_websocket_service import main
from util_run_logging import setupTestLogging


if __name__ == "__main__":
    setupTestLogging("test_client2_service")

    # Patch hostname resolution methods
    FileConfigDataExchange.serverHost = property(lambda self: "localhost")
    FileConfigTcpConnectTunnel.connectToHost = property(
        lambda self: "localhost"
    )
    FileConfigDataExchange._getOriginalServerHost = lambda self: "localhost"

    # Set config path to test_config/websocket_client_2
    configPath = (
        Path(__file__).parent.parent / "test_config" / "websocket_client_2"
    )

    # Set the home path for the service
    file_config.FileConfig.setHomePath(str(configPath))

    logger = logging.getLogger(__name__)
    logger.info("Starting TCP over WebSocket Test Client 2 Service")
    logger.info(f"Using config from: {configPath}")

    # Run the main service
    main()
