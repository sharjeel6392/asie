"""Middleware-level tests for the Prometheus instrumentation.

These deliberately build a throwaway FastAPI app rather than importing
src.serving.app: the real app loads models and connects to a database on
startup, none of which this behaviour depends on. Testing the middleware in
isolation is the reason it lives in its own module.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from prometheus_client import REGISTRY

from src.constants import METRICS_ROUTE, UNMATCHED_ROUTE_LABEL
from src.serving.metrics import metrics_middleware

REQUESTS_TOTAL = "asie_http_requests_total"
LATENCY_COUNT = "asie_http_request_duration_seconds_count"
IN_FLIGHT = "asie_http_requests_in_flight"


@pytest.fixture(scope="module")
def client():
    app = FastAPI()
    app.middleware("http")(metrics_middleware)

    @app.get("/ok")
    def ok():
        return {"ok": True}

    @app.get("/items/{item_id}")
    def item(item_id: str):
        return {"item_id": item_id}

    @app.get("/boom")
    def boom():
        raise RuntimeError("intentional")

    @app.get(METRICS_ROUTE)
    def metrics():
        return {"scrape": True}

    # raise_server_exceptions=False so an unhandled error surfaces as a 500
    # response instead of propagating, which is what a real client sees.
    return TestClient(app, raise_server_exceptions=False)


def counter(route, status, method="GET"):
    value = REGISTRY.get_sample_value(
        REQUESTS_TOTAL, {"method": method, "route": route, "status": status}
    )
    return value or 0.0


def latency_count(route, method="GET"):
    value = REGISTRY.get_sample_value(
        LATENCY_COUNT, {"method": method, "route": route}
    )
    return value or 0.0


def test_counts_successful_request(client):
    before = counter("/ok", "200")
    assert client.get("/ok").status_code == 200
    assert counter("/ok", "200") == before + 1


def test_records_latency(client):
    before = latency_count("/ok")
    client.get("/ok")
    assert latency_count("/ok") == before + 1


def test_labels_by_route_template_not_raw_path(client):
    """The cardinality guard: /items/1 and /items/2 must share one series."""
    before = counter("/items/{item_id}", "200")

    client.get("/items/1")
    client.get("/items/2")
    client.get("/items/3")

    assert counter("/items/{item_id}", "200") == before + 3
    # The raw paths must not have become series of their own.
    assert counter("/items/1", "200") == 0
    assert counter("/items/2", "200") == 0


def test_unmatched_paths_collapse_to_one_label(client):
    """404s from scanners/typos must not each create a time series."""
    before = counter(UNMATCHED_ROUTE_LABEL, "404")

    client.get("/nope")
    client.get("/also-nope")

    assert counter(UNMATCHED_ROUTE_LABEL, "404") == before + 2
    assert counter("/nope", "404") == 0


def test_unhandled_exception_counted_as_500(client):
    """The error-rate alert must not go quiet during the failure it watches."""
    before = counter("/boom", "500")
    assert client.get("/boom").status_code == 500
    assert counter("/boom", "500") == before + 1


def test_metrics_endpoint_excluded(client):
    """Scrape traffic would otherwise dominate request-rate graphs."""
    before = counter(METRICS_ROUTE, "200")
    client.get(METRICS_ROUTE)
    client.get(METRICS_ROUTE)
    assert counter(METRICS_ROUTE, "200") == before


def test_in_flight_returns_to_zero(client):
    """Decremented in a finally block, so errors must not leak the gauge."""
    client.get("/ok")
    client.get("/boom")
    assert REGISTRY.get_sample_value(IN_FLIGHT) == 0.0
