from src.utils.log_utils import get_logger


def test_get_logger_returns_logger():
    logger = get_logger("test_logger_unit")
    assert logger is not None
    assert logger.name == "test_logger_unit"
    assert logger.level <= 10  # DEBUG or lower


def test_get_logger_creates_log_directory(tmp_path):
    log_dir = tmp_path / "custom_logs"
    logger = get_logger("test_logger_dir", log_dir=str(log_dir))
    assert log_dir.exists()


def test_get_logger_does_not_duplicate_handlers():
    logger1 = get_logger("test_logger_unique")
    logger2 = get_logger("test_logger_unique")
    assert len(logger1.handlers) == len(logger2.handlers)


def test_get_logger_with_custom_filename(tmp_path):
    log_dir = tmp_path / "logs2"
    logger = get_logger("test_logger_file", log_dir=str(log_dir), log_file="custom.log", warn_log_file="custom_warn.log")
    assert logger is not None


def test_get_logger_default_values():
    logger = get_logger("test_default_vals")
    assert logger.level <= 10

