from prometheus_client import CollectorRegistry, Counter, Histogram

HTTP_LATENCY_BUCKETS = (
    0.005,
    0.01,
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.5,
    5.0,
    10.0,
)


class InventoryMetrics:
    def __init__(self) -> None:
        self.registry = CollectorRegistry(auto_describe=True)
        self.http_requests = Counter(
            "http_requests_total",
            "Total HTTP requests",
            labelnames=("method", "route", "status"),
            registry=self.registry,
        )
        self.http_latency = Histogram(
            "http_request_duration_seconds",
            "HTTP request latency in seconds",
            labelnames=("method", "route"),
            buckets=HTTP_LATENCY_BUCKETS,
            registry=self.registry,
        )
        self.http_errors = Counter(
            "http_error_responses_total",
            "HTTP responses with a 4xx or 5xx status",
            labelnames=("method", "route", "status"),
            registry=self.registry,
        )
        self.reservation_attempts = Counter(
            "inventory_reservation_attempts_total",
            "Inventory reservation attempts by outcome",
            labelnames=("outcome",),
            registry=self.registry,
        )
        self.units_reserved = Counter(
            "inventory_units_reserved_total",
            "Total units successfully reserved",
            registry=self.registry,
        )
        self.units_released = Counter(
            "inventory_units_released_total",
            "Total units released from expired or cancelled reservations",
            registry=self.registry,
        )
        self.products_created = Counter(
            "inventory_products_created_total",
            "Products created through the API",
            registry=self.registry,
        )

    def observe_http(
        self, *, method: str, route: str, status: int, duration_seconds: float
    ) -> None:
        self.http_requests.labels(method=method, route=route, status=str(status)).inc()
        self.http_latency.labels(method=method, route=route).observe(duration_seconds)
        if status >= 400:
            self.http_errors.labels(method=method, route=route, status=str(status)).inc()
