import logging
from pathlib import Path


def setupTestLogging(serviceName: str):
    """Setup logging to write to test-logs directory"""
    testLogsDir = Path(__file__).parent.parent / "test-logs"
    testLogsDir.mkdir(exist_ok=True)

    logFile = testLogsDir / f"{serviceName}.log"

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)s %(name)s:%(message)s",
        datefmt="%d-%b-%Y %H:%M:%S",
        handlers=[
            logging.FileHandler(logFile, mode="w"),
            logging.StreamHandler(),
        ],
    )

    logger = logging.getLogger(__name__)
    logger.info(f"{serviceName} logging to: {logFile}")
