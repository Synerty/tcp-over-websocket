import asyncio
import time
from typing import Optional

from tests.util_tcp_socket import UtilTcpSocket
from tests.util_tcp_socket import logger


class UtilDataSendEnsureReceivedConnection:
    """Manages one connection's send and receive data with timeout handling"""

    def __init__(self, name: str, data: bytes, timeout: float = 300.0):
        self.name = name
        self.data = data
        self.timeout = timeout
        self.receivedData = bytearray()
        self.success = False
        self.startTime = 0
        self.endTime = 0
        self.conn: Optional[UtilTcpSocket] = None
        self.clientId = 0
        self.sendComplete = False
        self.receiveComplete = False

    def setConnection(self, conn: UtilTcpSocket, clientId: int = 0):
        """Set the connection and client ID to use"""
        self.conn = conn
        self.clientId = clientId

    async def executeTransfer(self) -> tuple[bool, bytes, float]:
        """Execute the full transfer and return (success, received_data, throughput_mbps)"""
        if not self.conn:
            logger.error(f"{self.name}: No connection set")
            return False, b"", 0.0

        self.startTime = time.time()

        # Start send and receive tasks concurrently
        sendTask = asyncio.create_task(self._sendDataWithSteadyFlow())
        receiveTask = asyncio.create_task(self._receiveDataWithTimeout())

        try:
            await asyncio.gather(sendTask, receiveTask)
        except Exception as e:
            logger.error(f"{self.name}: Transfer failed: {e}")
            return False, b"", 0.0

        self.endTime = time.time()
        self.success = (
            self.sendComplete
            and self.receiveComplete
            and len(self.receivedData) == len(self.data)
        )

        # Calculate throughput
        duration = self.endTime - self.startTime
        totalBytes = len(self.data) * 2  # bidirectional
        throughputMbps = (
            (totalBytes / (1024 * 1024)) / duration if duration > 0 else 0
        )

        return self.success, bytes(self.receivedData), throughputMbps

    async def _sendDataWithSteadyFlow(self):
        """Send data in smaller chunks with more frequent yields for better socket processing"""
        chunkSize = 32 * 1024  # Reduced to 32KB chunks for better flow control
        sentBytes = 0
        lastActivityTime = time.time()

        while sentBytes < len(self.data):
            # Check for overall timeout
            if time.time() - self.startTime > self.timeout:
                logger.warning(
                    f"{self.name}: Send timeout after {self.timeout}s"
                )
                return

            endPos = min(sentBytes + chunkSize, len(self.data))
            chunk = self.data[sentBytes:endPos]

            if await self.conn.write(chunk, clientId=self.clientId):
                sentBytes += len(chunk)
                lastActivityTime = time.time()
                # More frequent yields for better concurrency
                await asyncio.sleep(0.005)  # 5ms yield to allow other tasks
            else:
                # Check if we've been inactive too long
                if time.time() - lastActivityTime > 10.0:
                    logger.error(f"{self.name}: Send stalled for 10s, aborting")
                    return
                await asyncio.sleep(0.2)  # Wait longer before retry

        self.sendComplete = True
        logger.debug(f"{self.name}: Send completed {sentBytes} bytes")

    async def _receiveDataWithTimeout(self):
        """Receive data with increased timeout and better flow control"""
        expectedBytes = len(self.data)
        lastActivityTime = time.time()
        noDataTimeout = min(300.0, self.timeout)  # Max 300s for no data

        while len(self.receivedData) < expectedBytes:
            # Check for overall timeout
            if time.time() - self.startTime > self.timeout:
                logger.warning(
                    f"{self.name}: Overall receive timeout after {self.timeout}s"
                )
                return

            # Check for no-data timeout
            if time.time() - lastActivityTime > noDataTimeout:
                logger.error(
                    f"{self.name}: Receive timeout after {noDataTimeout}s for clientId={self.clientId}"
                )
                return

            remaining = expectedBytes - len(self.receivedData)
            readSize = min(32 * 1024, remaining)  # Smaller read chunks

            try:
                chunk = await self.conn.read(
                    readSize, clientId=self.clientId, timeout=300.0
                )
                if chunk and len(chunk) > 0:
                    self.receivedData.extend(chunk)
                    lastActivityTime = time.time()
                    logger.debug(
                        f"{self.name}: Received {len(chunk)} bytes, total: {len(self.receivedData)}/{expectedBytes}"
                    )
                    # Yield more frequently during receive
                    await asyncio.sleep(0.001)  # 1ms yield
                else:
                    # No data received, wait and try again
                    await asyncio.sleep(0.1)
            except asyncio.TimeoutError:
                # Individual read timeout, continue if within overall limits
                await asyncio.sleep(0.2)
            except Exception as e:
                logger.error(f"{self.name}: Receive error: {e}")
                return

        self.receiveComplete = True
        logger.debug(
            f"{self.name}: Receive completed {len(self.receivedData)} bytes"
        )