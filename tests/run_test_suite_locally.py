#!/usr/bin/env python3

import logging
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import psutil

# Add the parent directory to Python path so we can import tcp_over_websocket
sys.path.insert(0, str(Path(__file__).parent.parent))

from util_port_config import get_port_config
from util_run_logging import setupTestLogging

print(
    """
Run Test Suite Locally

This python file orchestrates the whole test suite and services.

For development, run the services manually and run the required test to fix
manually.

"""
)

LOG_NAME = "run_test_suite"


class TcpOverWebsocketSubprocessManager:
    """Manages subprocess execution and output handling"""

    LOG_NAME = "TcpOverWebsocketSubprocessManager"

    def __init__(self):
        self.logger = logging.getLogger(f"{LOG_NAME}.{self.__class__.LOG_NAME}")
        self.loggerForProc = logging.getLogger(f"proc")
        self.processes = {}
        self.outputFiles = {}
        self.outputBuffers = {}
        self.readerThreads = {}
        self.stopReading = {}
        self.timestampPattern = re.compile(
            r"^\d{2}-\w{3}-\d{4} \d{2}:\d{2}:\d{2} (DEBUG|INFO|WARNING|ERROR)"
        )

    def writeOutput(self, outputDir: Path):
        """Write buffered data to files in the directory"""
        outputDir.mkdir(exist_ok=True)

        for serviceName, buffer in self.outputBuffers.items():
            if buffer:
                outputFile = outputDir / f"{serviceName}_output.log"
                with open(outputFile, "w") as f:
                    f.write("".join(buffer))
                self.logger.debug(f"Wrote {len(buffer)} lines to {outputFile}")

    def clearOutput(self):
        """Clear buffered data"""
        for serviceName in self.outputBuffers:
            self.outputBuffers[serviceName] = []
        self.logger.debug("Cleared all output buffers")

    def _streamReader(self, serviceName: str, stream, streamType: str):
        """Read from subprocess stream and buffer output"""
        while not self.stopReading.get(serviceName, False):
            try:
                line = stream.readline()
                if not line:
                    break

                # Buffer the original line
                if serviceName not in self.outputBuffers:
                    self.outputBuffers[serviceName] = []
                self.outputBuffers[serviceName].append(line)

                # Process line for logging
                processedLine = self._processLogLine(line.rstrip(), serviceName)
                if processedLine:
                    self._logProcessedLine(processedLine, serviceName)

            except Exception as e:
                self.logger.error(
                    f"Error reading {streamType} from {serviceName}: {e}"
                )
                break

    def _processLogLine(self, line: str, serviceName: str) -> str:
        """Process log line to strip timestamp and add service prefix"""
        if not line.strip():
            return ""

        # Check if line matches timestamp pattern
        match = self.timestampPattern.match(line)
        if match:
            # Strip timestamp and return just the message part
            logLevel = match.group(1)
            messageStart = match.end()
            message = line[messageStart:].strip()
            return f"{logLevel}: {message}"
        else:
            # Line doesn't match expected format, return as-is
            return line

    def _logProcessedLine(self, processedLine: str, serviceName: str):
        """Log the processed line with appropriate level and service prefix"""
        if processedLine.startswith("DEBUG:"):
            self.loggerForProc.debug(
                f"{serviceName}: {processedLine[6:].strip()}"
            )
        elif processedLine.startswith("INFO:"):
            self.loggerForProc.info(
                f"{serviceName}: {processedLine[5:].strip()}"
            )
        elif processedLine.startswith("WARNING:"):
            self.loggerForProc.warning(
                f"{serviceName}: {processedLine[8:].strip()}"
            )
        elif processedLine.startswith("ERROR:"):
            self.loggerForProc.error(
                f"{serviceName}: {processedLine[6:].strip()}"
            )
        else:
            self.loggerForProc.info(f"{serviceName}: {processedLine}")

    def startTestServices(self):
        """Start the three run_test services in subprocesses"""
        testsDir = Path(__file__).parent

        services = {
            "server": testsDir / "run_test_server_service.py",
            "client1": testsDir / "run_test_client1_service.py",
            "client2": testsDir / "run_test_client2_service.py",
        }

        self.logger.info("Starting test services")
        for serviceName, scriptPath in services.items():
            self.logger.info(f"Starting {serviceName} service: {scriptPath}")
            proc = subprocess.Popen(
                [sys.executable, str(scriptPath)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=1,
            )
            self.processes[serviceName] = proc
            self.outputBuffers[serviceName] = []
            self.stopReading[serviceName] = False

            # Start reader threads for stdout and stderr
            stdoutThread = threading.Thread(
                target=self._streamReader,
                args=(serviceName, proc.stdout, "stdout"),
                daemon=True,
            )
            stderrThread = threading.Thread(
                target=self._streamReader,
                args=(f"{serviceName}_stderr", proc.stderr, "stderr"),
                daemon=True,
            )

            stdoutThread.start()
            stderrThread.start()

            self.readerThreads[f"{serviceName}_stdout"] = stdoutThread
            self.readerThreads[f"{serviceName}_stderr"] = stderrThread

            self.logger.info(
                f"Started {serviceName} service with PID {proc.pid}"
            )

        # Wait a bit for services to start up
        self.logger.info("Waiting 10 seconds for services to initialize")
        time.sleep(10)

        # Check if all processes are still running
        for serviceName, proc in self.processes.items():
            if proc.poll() is not None:
                self.logger.error(
                    f"{serviceName} service failed to start (exit code: {proc.poll()})"
                )
                # Read any error output
                try:
                    output, _ = proc.communicate(timeout=1)
                    if output:
                        self.logger.error(f"{serviceName} output: {output}")
                except subprocess.TimeoutExpired:
                    pass
            else:
                self.logger.info(
                    f"{serviceName} service is running (PID {proc.pid})"
                )

        return self.processes

    def stopTestServices(self):
        """Stop the test services"""
        self.logger.info("Stopping test services")

        # Stop reader threads
        for serviceName in self.stopReading:
            self.stopReading[serviceName] = True

        for serviceName, proc in self.processes.items():
            if proc.poll() is None:  # Process is still running
                self.logger.info(
                    f"Terminating {serviceName} service (PID {proc.pid})"
                )
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                    self.logger.info(f"Terminated {serviceName} service")
                except subprocess.TimeoutExpired:
                    self.logger.warning(f"Force killing {serviceName} service")
                    proc.kill()
                    proc.wait()
            else:
                self.logger.info(f"{serviceName} service already stopped")

        # Wait for reader threads to finish
        for threadName, thread in self.readerThreads.items():
            if thread.is_alive():
                thread.join(timeout=2)

        self.readerThreads.clear()
        self.stopReading.clear()

    def captureServiceOutput(self, outputDir: Path):
        """Capture output from all services to files"""
        for serviceName, proc in self.processes.items():
            outputFile = outputDir / f"{serviceName}_service_output.log"
            self.outputFiles[serviceName] = open(outputFile, "w")
        return self.outputFiles


class KillExistingProcesses:
    """Checks for closed ports and running processes"""

    LOG_NAME = "KillExistingProcesses"

    def __init__(self):
        self.logger = logging.getLogger(f"{LOG_NAME}.{self.__class__.LOG_NAME}")

    def checkPortClosed(self, host: str, port: int) -> bool:
        """Check if a port is closed"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((host, port))
            sock.close()
            return result != 0  # Port is closed if connection failed
        except Exception:
            return True  # Assume closed if we can't check

    def ensurePortsClosed(self):
        """Ensure all ports from port_config are closed"""
        portConfig = get_port_config()

        ports_to_check = [
            ("localhost", portConfig.serverToClientTun1ListenPort),
            ("localhost", portConfig.serverToClientTun2ListenPort),
            ("localhost", portConfig.client1ToServerTun1ListenPort),
            ("localhost", portConfig.client1ToServerTun2ListenPort),
            ("localhost", portConfig.client2ToServerTun1ListenPort),
            ("localhost", portConfig.client2ToServerTun2ListenPort),
            ("localhost", portConfig.serverWebsocketPort),
        ]

        self.logger.info("Checking that all required ports are closed")
        for host, port in ports_to_check:
            if not self.checkPortClosed(host, port):
                self.logger.warning(f"Port {host}:{port} is still open")
            else:
                self.logger.debug(f"Port {host}:{port} is closed")

    def killRunTestProcesses(self):
        """Kill any existing run_test_* processes using ps"""
        self.logger.info("Checking for existing run_test_* processes")
        killed_processes = []

        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                cmdline = proc.info["cmdline"]
                if cmdline and any("run_test_" in arg for arg in cmdline):
                    if any(
                        service in " ".join(cmdline)
                        for service in [
                            "server_service",
                            "client1_service",
                            "client2_service",
                        ]
                    ):
                        self.logger.info(
                            f"Killing process {proc.info['pid']}: {' '.join(cmdline)}"
                        )
                        proc.kill()
                        killed_processes.append(proc.info["pid"])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        if killed_processes:
            self.logger.info(
                f"Killed {len(killed_processes)} run_test_* processes"
            )
            time.sleep(2)  # Wait for processes to die
        else:
            self.logger.info("No existing run_test_* processes found")


class SequentialTestRunner:
    """Runs the sequential tests using subprocess management and port checking"""

    LOG_NAME = "SequentialTestRunner"

    def __init__(self):
        self.logger = logging.getLogger(f"{LOG_NAME}.{self.__class__.LOG_NAME}")
        self.subprocessManager = TcpOverWebsocketSubprocessManager()
        self.portChecker = KillExistingProcesses()

    def removeAllLogFiles(self):
        """Remove all log files from test-logs directory"""
        testLogsDir = Path(__file__).parent.parent / "test-logs"

        if testLogsDir.exists():
            self.logger.info("Removing all existing log files")
            for logFile in testLogsDir.glob("*"):
                if logFile.is_file():
                    logFile.unlink()
                    self.logger.debug(f"Removed log file: {logFile}")
                elif logFile.is_dir():
                    shutil.rmtree(logFile)
                    self.logger.debug(f"Removed log directory: {logFile}")
        else:
            testLogsDir.mkdir(exist_ok=True)
            self.logger.info("Created test-logs directory")

    def runIndividualTest(self, testFile: Path, processes: dict) -> bool:
        """Run an individual pytest and capture service outputs"""
        testName = testFile.stem

        self.logger.info(f"Running test: {testName}")

        # Create test-specific directory
        testLogsDir = Path(__file__).parent.parent / "test-logs" / testName
        testLogsDir.mkdir(exist_ok=True)

        # Capture service output during test
        serviceOutputFiles = self.subprocessManager.captureServiceOutput(
            testLogsDir
        )

        try:
            # Run the specific test
            cmd = [
                sys.executable,
                "-m",
                "pytest",
                str(testFile),
                "-v",
                "--asyncio-mode=auto",
                "--tb=short",
                "-ra",
                "--maxfail=1",
            ]

            testLogFile = testLogsDir / f"{testName}.log"

            # Run test and capture output
            testProcess = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=Path(__file__).parent,
                universal_newlines=True,
                bufsize=1,
            )

            # Buffer test output
            testOutputBuffer = []

            # Start threads to read test output
            def readTestOutput(stream, streamName):
                while True:
                    line = stream.readline()
                    if not line:
                        break
                    testOutputBuffer.append(line)
                    # Process and log test output
                    processedLine = self.subprocessManager._processLogLine(
                        line.rstrip(), "test"
                    )
                    if processedLine:
                        self.subprocessManager._logProcessedLine(
                            processedLine, "test"
                        )

            stdoutThread = threading.Thread(
                target=readTestOutput,
                args=(testProcess.stdout, "stdout"),
                daemon=True,
            )
            stderrThread = threading.Thread(
                target=readTestOutput,
                args=(testProcess.stderr, "stderr"),
                daemon=True,
            )

            stdoutThread.start()
            stderrThread.start()

            # Wait for test to complete
            try:
                result = testProcess.wait(timeout=1800)
            except subprocess.TimeoutExpired:
                testProcess.kill()
                raise

            # Wait for output threads to finish
            stdoutThread.join(timeout=2)
            stderrThread.join(timeout=2)

            # Write test output to file
            with open(testLogFile, "w") as logFile:
                logFile.writelines(testOutputBuffer)

            # Create result object with returncode
            class TestResult:
                def __init__(self, returncode):
                    self.returncode = returncode

            result = TestResult(result)

            # Copy the test log
            self.logger.info(
                f"Test {testName} completed with exit code {result.returncode}"
            )

            # Close service output files
            for outputFile in serviceOutputFiles.values():
                outputFile.close()

            return result.returncode == 0

        except subprocess.TimeoutExpired:
            self.logger.error(f"Test {testName} timed out after 30 minutes")
            return False
        except Exception as e:
            self.logger.error(f"Test {testName} failed with exception: {e}")
            return False
        finally:
            # Ensure service output files are closed
            for outputFile in serviceOutputFiles.values():
                try:
                    outputFile.close()
                except:
                    pass

    def discoverTestFiles(self) -> list:
        """Discover all test suite files"""
        testsDir = Path(__file__).parent
        testFiles = []

        # Look for test_suite_*.py files in order
        for i in range(1, 8):  # Suites 1-7
            pattern = f"test_suite_{i}_*.py"
            matches = list(testsDir.glob(pattern))
            testFiles.extend(sorted(matches))

        return testFiles

    def runAllTests(self) -> bool:
        """Run all tests with service management"""
        # Clean up previous runs
        self.removeAllLogFiles()
        self.portChecker.ensurePortsClosed()
        self.portChecker.killRunTestProcesses()

        # Start services
        processes = self.subprocessManager.startTestServices()

        try:
            # Discover and run tests
            testFiles = self.discoverTestFiles()
            self.logger.info(f"Discovered {len(testFiles)} test files")

            totalTests = len(testFiles)
            passedTests = 0
            failedTests = 0

            for testFile in testFiles:
                success = self.runIndividualTest(testFile, processes)
                if success:
                    passedTests += 1
                else:
                    failedTests += 1

                self.logger.info(
                    f"Progress: {passedTests + failedTests}/{totalTests} tests completed"
                )

            self.logger.info(
                f"Test run complete: {passedTests} passed, {failedTests} failed"
            )
            return failedTests == 0

        finally:
            # Always stop services
            self.subprocessManager.stopTestServices()
            self.subprocessManager.clearOutput()


if __name__ == "__main__":
    setupTestLogging("run_test_suite")

    logger = logging.getLogger(LOG_NAME)
    logger.info("Starting TCP over WebSocket Test Suite Runner")

    try:
        testRunner = SequentialTestRunner()
        success = testRunner.runAllTests()
        if success:
            logger.info("All tests passed successfully")
            sys.exit(0)
        else:
            logger.error("Some tests failed")
            sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Test suite runner interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Test suite runner failed: {e}")
        sys.exit(1)
