from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.tracing import TraceIdMiddleware, get_trace_id, new_trace_id


def test_new_trace_id_is_unique_hex():
    first = new_trace_id()
    second = new_trace_id()
    assert first != second
    assert len(first) == 32
    int(first, 16)


def test_get_trace_id_default():
    assert get_trace_id() == "-"


def test_trace_id_middleware_propagates_header_and_context():
    app = FastAPI()
    app.add_middleware(TraceIdMiddleware)

    @app.get("/")
    def probe():
        return {"trace_id": get_trace_id()}

    with TestClient(app) as client:
        response = client.get("/", headers={"X-Trace-Id": "known-trace"})
    assert response.status_code == 200
    assert response.json()["trace_id"] == "known-trace"
    assert response.headers["X-Trace-Id"] == "known-trace"
