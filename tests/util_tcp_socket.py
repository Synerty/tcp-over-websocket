import asyncio
import logging
import os
from enum import Enum
from typing import Awaitable
from typing import Callable
from typing import Dict
from typing import Optional
from typing import Tuple

logger = logging.getLogger(__name__)


class ConnectionEndState(Enum):
    EXPECTED_FAILOVER = "expected_failover"
    EXPECTED_TEST_END = "expected_test_end"
    UNEXPECTED_CLOSE = "unexpected_close"


class UtilTcpSocket:
    def __init__(
        self,
        name: str,
        shouldEchoData: bool = False,
        logTrafficEvents: bool = True,
    ):
        self.name = name
        self.shouldEchoData = shouldEchoData
        self.logTrafficEvents = logTrafficEvents
        self.server: Optional[asyncio.Server] = None
        self.expectedEndState = ConnectionEndState.UNEXPECTED_CLOSE
        self.host: Optional[str] = None
        self.port: Optional[int] = None

        # Client connections indexed by clientId (0 for startConnect, unique IDs for listen mode)
        self.readers: Dict[int, asyncio.StreamReader] = {}
        self.writers: Dict[int, asyncio.StreamWriter] = {}
        self.echoTasks: Dict[int, asyncio.Task] = {}
        self.nextClientId: int = 1

        # Callback for when new clients connect in listen mode
        self.onClientConnected: Optional[Callable[[int], Awaitable[None]]] = (
            None
        )

    def setExpectedEndState(self, state: ConnectionEndState):
        """Set the expected end state for this connection"""
        self.expectedEndState = state
        logger.info(f"{self.name}: Expected end state set to {state.value}")

    def setOnClientConnected(self, callback: Callable[[int], Awaitable[None]]):
        """Set callback to be called when a new client connects"""
        self.onClientConnected = callback

    async def startConnect(
        self, host: str, port: int, timeout: float = 30.0
    ) -> bool:
        """Connect to a remote host and port - always uses clientId 0"""
        if 0 in self.readers:
            logger.error(f"{self.name}: Already connected")
            return False

        if "HOST_DOCKERNAMES" not in os.environ:
            host = "127.0.0.1"

        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=timeout
            )
            self.readers[0] = reader
            self.writers[0] = writer
            self.host = host
            self.port = port
            if self.logTrafficEvents:
                logger.info(
                    f"{self.name}: Connected to {host}:{port} (clientId=0)"
                )
            return True
        except asyncio.TimeoutError:
            logger.error(
                f"{self.name}: Connection timeout to {host}:{port} after {timeout}s"
            )
            return False
        except Exception as e:
            logger.exception(
                f"{self.name}: Failed to connect to {host}:{port}: {e}"
            )
            return False

    async def startListen(self, port: int, host: str = "localhost") -> bool:
        """Start listening on a port for incoming connections"""
        if self.server:
            logger.error(f"{self.name}: Already listening")
            return False

        try:
            self.server = await asyncio.start_server(
                self._handleClientConnection, host, port
            )
            await asyncio.sleep(0.1)
            self.host = host
            self.port = port
            if self.logTrafficEvents:
                logger.info(f"{self.name}: Listening on {host}:{port}")
            return True
        except Exception as e:
            logger.exception(
                f"{self.name}: Failed to start listening on {host}:{port}: {e}"
            )
            return False

    async def _handleClientConnection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ):
        """Handle incoming client connection"""
        clientHost, clientPort = writer.get_extra_info("peername")
        clientId = self.nextClientId
        self.nextClientId += 1

        self.readers[clientId] = reader
        self.writers[clientId] = writer
        if self.logTrafficEvents:
            logger.info(
                f"{self.name}: Client connected from {clientHost}:{clientPort} (clientId={clientId})"
            )

        if self.shouldEchoData:
            self.echoTasks[clientId] = asyncio.create_task(
                self._echoTaskForClient(clientId)
            )
            if self.logTrafficEvents:
                logger.info(
                    f"{self.name}: Echo task started for clientId={clientId}"
                )

        if self.onClientConnected:
            try:
                await self.onClientConnected(clientId)
            except Exception as e:
                logger.exception(
                    f"{self.name}: Error in onClientConnected callback for clientId={clientId}: {e}"
                )

    async def _echoTaskForClient(self, clientId: int):
        """Echo back any received data for a specific client"""
        try:
            while clientId in self.readers:
                try:
                    reader = self.readers[clientId]
                    writer = self.writers[clientId]
                    data = await reader.read(4096)
                    if not data:
                        break

                    writer.write(data)
                    await writer.drain()
                    if self.logTrafficEvents:
                        logger.debug(
                            f"{self.name}: Echoed {len(data)} bytes to clientId={clientId}"
                        )
                except (
                    BrokenPipeError,
                    ConnectionResetError,
                    ConnectionAbortedError,
                ) as e:
                    self._handleConnectionError(e, f"echo-client{clientId}")
                    break
                except Exception as e:
                    logger.exception(
                        f"{self.name}: Echo task error for clientId={clientId}: {e}"
                    )
                    break
        finally:
            if clientId in self.readers:
                del self.readers[clientId]
            if clientId in self.writers:
                writer = self.writers[clientId]
                del self.writers[clientId]
                try:
                    writer.close()
                    await writer.wait_closed()
                except:
                    pass
            if clientId in self.echoTasks:
                del self.echoTasks[clientId]
            if self.logTrafficEvents:
                logger.info(
                    f"{self.name}: Echo task ended for clientId={clientId}"
                )

    def getReader(self, clientId: int = 0) -> Optional[asyncio.StreamReader]:
        """Get the StreamReader for a specific client"""
        return self.readers.get(clientId)

    def getWriter(self, clientId: int = 0) -> Optional[asyncio.StreamWriter]:
        """Get the StreamWriter for a specific client"""
        return self.writers.get(clientId)

    def isConnected(self, clientId: int = 0) -> bool:
        """Check if a specific client is connected"""
        return clientId in self.readers and clientId in self.writers

    async def read(
        self, size: int = -1, clientId: int = 0, timeout: float = 300.0
    ) -> Optional[bytes]:
        """Read data from a specific client socket"""
        if not self.isConnected(clientId):
            logger.error(
                f"{self.name}: Cannot read - clientId={clientId} not connected"
            )
            return None

        reader = self.readers[clientId]
        try:
            if size == -1:
                data = await asyncio.wait_for(reader.read(), timeout=timeout)
            else:
                data = await asyncio.wait_for(
                    reader.read(size), timeout=timeout
                )

            if not data:
                self._handleConnectionClosed(f"read-client{clientId} - no data")
                return None
            return data
        except (
            BrokenPipeError,
            ConnectionResetError,
            ConnectionAbortedError,
        ) as e:
            self._handleConnectionError(e, f"read-client{clientId}")
            return None
        except asyncio.TimeoutError:
            logger.error(
                f"{self.name}: Receive timeout after {timeout}s for clientId={clientId}"
            )
            return None
        except Exception as e:
            logger.exception(
                f"{self.name}: Unexpected read error for clientId={clientId}: {e}"
            )
            return None

    async def write(self, data: bytes, clientId: int = 0) -> bool:
        """Write data to a specific client socket"""
        if not self.isConnected(clientId):
            logger.error(
                f"{self.name}: Cannot write - clientId={clientId} not connected"
            )
            return False

        writer = self.writers[clientId]
        try:
            writer.write(data)
            await writer.drain()
            # Small yield for better concurrency under high load
            await asyncio.sleep(0.001)
            return True

        except (
            BrokenPipeError,
            ConnectionResetError,
            ConnectionAbortedError,
        ) as e:
            self._handleConnectionError(e, f"write-client{clientId}")
            return False

        except Exception as e:
            logger.exception(
                f"{self.name}: Unexpected write error for clientId={clientId}: {e}"
            )
            return False

    async def _echoSend(
        self, data: bytes, timeout: float = 300.0, clientId: int = 0
    ) -> bool:
        """Send data through a specific client connection with timeout"""
        if not self.isConnected(clientId):
            logger.error(
                f"{self.name}: Cannot send - clientId={clientId} not connected"
            )
            return False

        writer = self.writers[clientId]
        try:
            writer.write(data)
            await asyncio.wait_for(writer.drain(), timeout=timeout)
            return True
        except (
            BrokenPipeError,
            ConnectionResetError,
            ConnectionAbortedError,
        ) as e:
            self._handleConnectionError(e, f"send-client{clientId}")
            return False

        except asyncio.TimeoutError:
            logger.error(
                f"{self.name}: Send timeout after {timeout}s for clientId={clientId}"
            )
            return False

        except Exception as e:
            logger.exception(
                f"{self.name}: Unexpected send error for clientId={clientId}: {e}"
            )
            return False

    async def _echoReceive(
        self, size: int, timeout: float = 300.0, clientId: int = 0
    ) -> Optional[bytes]:
        """Receive data from a specific client connection with timeout"""
        if not self.isConnected(clientId):
            logger.error(
                f"{self.name}: Cannot receive - clientId={clientId} not connected"
            )
            return None

        reader = self.readers[clientId]
        try:
            data = await asyncio.wait_for(reader.read(size), timeout=timeout)
            if not data:
                self._handleConnectionClosed(
                    f"receive-client{clientId} - no data"
                )
                return None
            return data
        except (
            BrokenPipeError,
            ConnectionResetError,
            ConnectionAbortedError,
        ) as e:
            self._handleConnectionError(e, f"receive-client{clientId}")
            return None
        except asyncio.TimeoutError:
            logger.error(
                f"{self.name}: Receive timeout after {timeout}s for clientId={clientId}"
            )
            return None
        except Exception as e:
            logger.exception(
                f"{self.name}: Unexpected receive error for clientId={clientId}: {e}"
            )
            return None

    async def sendDataExpectEcho(
        self, data: bytes, timeout: float = 300.0, clientId: int = 0
    ) -> Tuple[bytes, bool]:
        """Send data and receive echo response for a specific client"""
        if not await self._echoSend(data, timeout, clientId):
            return b"", False

        receivedData = b""
        while len(receivedData) < len(data):
            chunk = await self._echoReceive(
                len(data) - len(receivedData), timeout, clientId
            )
            if chunk is None:
                break
            receivedData += chunk

        success = len(receivedData) == len(data) and receivedData == data
        if success:
            if self.logTrafficEvents:
                logger.info(
                    f"{self.name}: Successfully sent and received {len(data)} bytes for clientId={clientId}"
                )
        else:
            # Enhanced logging for data mismatches
            if len(receivedData) != len(data):
                logger.warning(
                    f"{self.name}: Data length mismatch for clientId={clientId}: sent {len(data)}, received {len(receivedData)}"
                )

            if len(receivedData) > 0 and receivedData != data:
                logger.warning(
                    f"{self.name}: Data content mismatch for clientId={clientId}"
                )

            # Log the actual data for debugging
            def formatDataForLogging(dataBytes: bytes, label: str) -> str:
                if len(dataBytes) == 0:
                    return f"{label}: <empty>"
                elif len(dataBytes) <= 50:
                    # Show both string and hex for short data
                    try:
                        strRepr = dataBytes.decode("utf-8", errors="replace")
                        if strRepr.isprintable():
                            return (
                                f"{label}: '{strRepr}' (hex: {dataBytes.hex()})"
                            )
                        else:
                            return f"{label}: <non-printable> (hex: {dataBytes.hex()})"
                    except:
                        return (
                            f"{label}: <decode-error> (hex: {dataBytes.hex()})"
                        )
                else:
                    # Show first 25 bytes for long data
                    try:
                        prefix = dataBytes[:25]
                        strRepr = prefix.decode("utf-8", errors="replace")
                        if strRepr.isprintable():
                            return f"{label}: '{strRepr}...' (hex: {prefix.hex()}...) [{len(dataBytes)} bytes total]"
                        else:
                            return f"{label}: <non-printable> (hex: {prefix.hex()}...) [{len(dataBytes)} bytes total]"
                    except:
                        return f"{label}: <decode-error> (hex: {dataBytes[:25].hex()}...) [{len(dataBytes)} bytes total]"

            logger.warning(formatDataForLogging(data, "Expected data"))
            logger.warning(formatDataForLogging(receivedData, "Received data"))

        return receivedData, success

    async def close(self, clientId: Optional[int] = None):
        """Close connection(s). If clientId specified, close that client. Otherwise close all."""
        if clientId is not None:
            await self._closeClient(clientId)
        else:
            for cid in list(self.echoTasks.keys()):
                task = self.echoTasks.get(cid)
                if not task:
                    continue

                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
            self.echoTasks.clear()

            for cid in list(self.writers.keys()):
                await self._closeClient(cid)

            if self.server:
                try:
                    self.server.close()
                    await self.server.wait_closed()
                    if self.logTrafficEvents:
                        logger.info(f"{self.name}: Server stopped")
                except Exception as e:
                    logger.exception(f"{self.name}: Error stopping server: {e}")
                self.server = None

    async def _closeClient(self, clientId: int):
        """Close a specific client connection"""
        if clientId in self.echoTasks:
            task = self.echoTasks[clientId]
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            del self.echoTasks[clientId]

        if clientId in self.readers:
            del self.readers[clientId]

        if clientId in self.writers:
            writer = self.writers[clientId]
            del self.writers[clientId]
            try:
                if not writer.is_closing():
                    writer.close()
                    await writer.wait_closed()
                if self.logTrafficEvents:
                    logger.info(
                        f"{self.name}: Connection closed for clientId={clientId}"
                    )
            except (
                BrokenPipeError,
                ConnectionResetError,
                ConnectionAbortedError,
            ) as e:
                self._handleConnectionError(e, f"close-client{clientId}")
            except Exception as e:
                logger.exception(
                    f"{self.name}: Unexpected close error for clientId={clientId}: {e}"
                )

    def isClosing(self, clientId: int = 0) -> bool:
        """Check if a specific client writer is closing"""
        writer = self.writers.get(clientId)
        return writer.is_closing() if writer else True

    def _handleConnectionError(self, error: Exception, operation: str):
        """Handle connection errors with appropriate logging based on expected state"""
        errorType = type(error).__name__

        if self.expectedEndState == ConnectionEndState.EXPECTED_FAILOVER:
            logger.info(
                f"{self.name}: Expected connection error during {operation} (failover): {errorType}"
            )
        elif self.expectedEndState == ConnectionEndState.EXPECTED_TEST_END:
            logger.info(
                f"{self.name}: Expected connection error during {operation} (test ending): {errorType}"
            )
        else:
            logger.exception(
                f"{self.name}: Unexpected connection error during {operation}: {errorType}"
            )

    def _handleConnectionClosed(self, operation: str):
        """Handle connection closed scenarios"""
        if self.expectedEndState == ConnectionEndState.EXPECTED_FAILOVER:
            logger.info(
                f"{self.name}: Connection closed during {operation} (failover)"
            )
        elif self.expectedEndState == ConnectionEndState.EXPECTED_TEST_END:
            logger.info(
                f"{self.name}: Connection closed during {operation} (test ending)"
            )
        else:
            logger.exception(
                f"{self.name}: Connection unexpectedly closed during {operation}"
            )
