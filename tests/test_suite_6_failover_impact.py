import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging


logger = logging.getLogger(__name__)


class TestFailoverImpact:
    pass
