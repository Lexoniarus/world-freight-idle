import json
import logging

from app.logging_config import JsonFormatter, configure_logging


def test_json_formatter_includes_structured_fields():
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )
    record.event = "demo.event"
    record.data = {"answer": 42}
    payload = json.loads(formatter.format(record))
    assert payload["message"] == "hello"
    assert payload["event"] == "demo.event"
    assert payload["data"] == {"answer": 42}
    assert "trace_id" in payload


def test_configure_logging_replaces_root_handler():
    configure_logging("WARNING")
    root = logging.getLogger()
    assert root.level == logging.WARNING
    assert len(root.handlers) == 1
    assert isinstance(root.handlers[0].formatter, JsonFormatter)


def test_json_formatter_includes_exception_details():
    formatter = JsonFormatter()
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        exc_info = sys.exc_info()
    record = logging.LogRecord(
        name="test",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="failed",
        args=(),
        exc_info=exc_info,
    )
    payload = json.loads(formatter.format(record))
    assert "ValueError: boom" in payload["exception"]
