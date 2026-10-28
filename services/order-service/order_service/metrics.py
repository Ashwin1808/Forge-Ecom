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


class OrderMetrics:
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
        self.order_attempts = Counter(
            "order_creation_attempts_total",
            "Order creation attempts by outcome",
            labelnames=("outcome",),
            registry=self.registry,
        )
        self.checkout_attempts = Counter(
            "checkout_attempts_total",
            "Storefront checkout attempts by outcome",
            labelnames=("outcome",),
            registry=self.registry,
        )
        self.expired_orders = Counter(
            "checkout_orders_expired_total",
            "Storefront checkout reservations expired",
            registry=self.registry,
        )
        self.downstream_requests = Counter(
            "downstream_requests_total",
            "Calls to downstream services",
            labelnames=("target", "operation", "outcome"),
            registry=self.registry,
        )
        self.downstream_latency = Histogram(
            "downstream_request_duration_seconds",
            "Downstream service call latency",
            labelnames=("target", "operation"),
            buckets=HTTP_LATENCY_BUCKETS,
            registry=self.registry,
        )

    def observe_http(
        self, *, method: str, route: str, status: int, duration_seconds: float
    ) -> None:
        self.http_requests.labels(method=method, route=route, status=str(status)).inc()
        self.http_latency.labels(method=method, route=route).observe(duration_seconds)
        if status >= 400:
            self.http_errors.labels(method=method, route=route, status=str(status)).inc()
