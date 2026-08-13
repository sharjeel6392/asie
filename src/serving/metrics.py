"""Prometheus instrumentation for the serving API.

Kept out of app.py so the collectors can be imported and asserted on in tests
without standing up the whole FastAPI app (which loads models on startup).

Single-process only: the image runs uvicorn with one worker, so the default
global registry is correct. If `--workers` is ever added, each worker would
keep its own counts and /metrics would return whichever worker answered the
scrape -- at that point this needs prometheus_client's multiprocess mode
(PROMETHEUS_MULTIPROC_DIR + MultiProcessCollector), not just more workers.
"""

import time

from prometheus_client import Counter, Gauge, Histogram
from starlette.requests import Request

from src.constants import (
    DRIFT_METRIC_DESCRIPTION,
    DRIFT_METRIC_NAME,
    DRIFT_UPDATED_METRIC_DESCRIPTION,
    DRIFT_UPDATED_METRIC_NAME,
    HTTP_IN_FLIGHT_METRIC_DESCRIPTION,
    HTTP_IN_FLIGHT_METRIC_NAME,
    HTTP_LATENCY_BUCKETS,
    HTTP_LATENCY_METRIC_DESCRIPTION,
    HTTP_LATENCY_METRIC_NAME,
    HTTP_REQUESTS_METRIC_DESCRIPTION,
    HTTP_REQUESTS_METRIC_NAME,
    METRICS_ROUTE,
    MODEL_LOADED_METRIC_DESCRIPTION,
    MODEL_LOADED_METRIC_NAME,
    UNMATCHED_ROUTE_LABEL,
)

request_count = Counter(
    HTTP_REQUESTS_METRIC_NAME,
    HTTP_REQUESTS_METRIC_DESCRIPTION,
    ["method", "route", "status"],
)

request_latency = Histogram(
    HTTP_LATENCY_METRIC_NAME,
    HTTP_LATENCY_METRIC_DESCRIPTION,
    ["method", "route"],
    buckets=HTTP_LATENCY_BUCKETS,
)

requests_in_flight = Gauge(
    HTTP_IN_FLIGHT_METRIC_NAME,
    HTTP_IN_FLIGHT_METRIC_DESCRIPTION,
)

model_loaded = Gauge(
    MODEL_LOADED_METRIC_NAME,
    MODEL_LOADED_METRIC_DESCRIPTION,
    ["role"],
)

drift_gauge = Gauge(
    DRIFT_METRIC_NAME,
    DRIFT_METRIC_DESCRIPTION,
)

drift_last_updated = Gauge(
    DRIFT_UPDATED_METRIC_NAME,
    DRIFT_UPDATED_METRIC_DESCRIPTION,
)


def route_label(request: Request) -> str:
    """The templated path for a request, e.g. "/predict" -- never the raw URL.

    Labelling by `request.url.path` would mean every unmatched URL a scanner
    or a typo produces becomes its own time series, and any future path
    parameter (`/models/{id}`) would create one series per id. Either way the
    metric grows without bound and eventually takes Prometheus down with it.

    Starlette records the matched route on the scope during routing, but the
    key it uses has moved between versions, so fall back through the options
    and finally to a single constant label for anything unmatched.
    """
    scope = request.scope

    route = scope.get("route")
    if route is not None:
        # APIRoute/Route expose the template as path_format; plain Mounts
        # only have .path.
        path_format = getattr(route, "path_format", None) or getattr(route, "path", None)
        if path_format:
            return str(path_format)

    endpoint = scope.get("endpoint")
    if endpoint is not None:
        name = getattr(endpoint, "__name__", None)
        if name:
            return name

    return UNMATCHED_ROUTE_LABEL


async def metrics_middleware(request: Request, call_next):
    """Record count and latency for each request.

    /metrics is deliberately excluded. Prometheus scrapes it every 30s per
    replica, which on a low-traffic service would dominate the request-rate
    graphs and make real user traffic invisible.
    """
    if request.url.path == METRICS_ROUTE:
        return await call_next(request)

    start = time.perf_counter()
    requests_in_flight.inc()
    status = "500"
    try:
        response = await call_next(request)
        status = str(response.status_code)
        return response
    except Exception:
        # An unhandled exception still becomes a 500 to the client, so it has
        # to be counted as one -- otherwise the error-rate alert goes quiet
        # during exactly the failure it exists to catch.
        raise
    finally:
        elapsed = time.perf_counter() - start
        requests_in_flight.dec()
        # Resolved after call_next, since routing is what populates the scope.
        label = route_label(request)
        request_count.labels(
            method=request.method, route=label, status=status
        ).inc()
        request_latency.labels(method=request.method, route=label).observe(elapsed)
