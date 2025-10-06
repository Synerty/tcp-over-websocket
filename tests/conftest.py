import logging
from pathlib import Path

import pytest


@pytest.fixture(scope="module", autouse=True)
def setupModuleLogging(request):
    """Setup logging for each test module"""

    logDir = Path(__file__).parent.parent / "test-logs"
    logDir.mkdir(exist_ok=True)

    moduleName = request.module.__name__.replace("tests.", "")
    logFile = logDir / f"{moduleName}.log"

    # Create file handler for this module
    fileHandler = logging.FileHandler(logFile, mode="w")
    fileHandler.setLevel(logging.INFO)
    fileHandler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s:%(message)s",
            datefmt="%d-%b-%Y %H:%M:%S",
        )
    )

    # Add handler to root logger
    rootLogger = logging.getLogger()
    rootLogger.addHandler(fileHandler)

    logger = logging.getLogger(__name__)
    logger.info(f"Module {moduleName} logging to: {logFile}")

    yield

    # Remove handler after module tests complete
    rootLogger.removeHandler(fileHandler)
    fileHandler.close()
