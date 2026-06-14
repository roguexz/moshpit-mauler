import os
from moshpit import __version__
from moshpit.exceptions import MoshpitException
from moshpit.logger import setup_logger


def test_version():
    assert __version__ == "0.1.0"


def test_exceptions():
    assert issubclass(MoshpitException, Exception)


def test_logger(tmp_path):
    log_file = tmp_path / "test_run.log"
    setup_logger(str(log_file), level="DEBUG")
    # Log something to verify
    from loguru import logger

    logger.debug("Testing log output")
    assert os.path.exists(str(log_file))
