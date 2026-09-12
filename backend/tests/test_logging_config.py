import logging

from app.logging_config import _SuppressManagementApiAccessLogs


def _make_record(message: str) -> logging.LogRecord:
    return logging.LogRecord(
        name="uvicorn.access", level=logging.INFO, pathname=__file__, lineno=1, msg=message, args=(), exc_info=None
    )


def test_filters_out_management_api_requests():
    f = _SuppressManagementApiAccessLogs()
    record = _make_record('127.0.0.1:1234 - "GET /api/dashboard/rds-status HTTP/1.1" 200')
    assert f.filter(record) is False


def test_keeps_nmos_api_requests():
    f = _SuppressManagementApiAccessLogs()
    record = _make_record('127.0.0.1:1234 - "GET /x-nmos/node/v1.3/senders HTTP/1.1" 200')
    assert f.filter(record) is True
