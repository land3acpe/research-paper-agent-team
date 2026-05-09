import json

from src.logging_config import configure_logging


def test_configure_logging_returns_logger(tmp_path):
    log_file = tmp_path / "test.log"
    logger = configure_logging(log_level="info", log_file=str(log_file))
    assert logger is not None


def test_logging_writes_json_to_file(tmp_path):
    log_file = tmp_path / "test.log"
    logger = configure_logging(log_level="info", log_file=str(log_file))
    logger.info("test_event", run_id="abc", count=42)
    content = log_file.read_text()
    record = json.loads(content.strip().splitlines()[-1])
    assert record["event"] == "test_event"
    assert record["run_id"] == "abc"
    assert record["count"] == 42
