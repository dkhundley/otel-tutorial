from __future__ import annotations

import logging
import os
import sys

from opentelemetry import metrics, trace
from opentelemetry.sdk.resources import Resource

# Traces
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

# Metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import ConsoleMetricExporter, PeriodicExportingMetricReader

SERVICE_NAME = "pizza-otel-demo"


def configure_otel() -> None:
    resource = Resource.create({"service.name": SERVICE_NAME})
    running_under_pytest = "PYTEST_CURRENT_TEST" in os.environ

    # Trace provider
    tracer_provider = TracerProvider(resource=resource)
    if not running_under_pytest:
        tracer_provider.add_span_processor(
            BatchSpanProcessor(ConsoleSpanExporter(out=sys.__stdout__))
        )
    trace.set_tracer_provider(tracer_provider)

    # Meter provider
    metric_readers = []
    if not running_under_pytest:
        metric_readers.append(
            PeriodicExportingMetricReader(
                ConsoleMetricExporter(out=sys.__stdout__),
                export_interval_millis=5000,
            )
        )
    meter_provider = MeterProvider(
        resource=resource,
        metric_readers=metric_readers,
    )
    metrics.set_meter_provider(meter_provider)

    # Use standard logging to avoid deprecated OpenTelemetry SDK logging handler APIs.
    handler = logging.StreamHandler(stream=sys.__stdout__)
    handler.setLevel(logging.INFO)
    app_logger = logging.getLogger("pizza_api")
    app_logger.setLevel(logging.INFO)
    app_logger.handlers.clear()
    app_logger.addHandler(handler)
    app_logger.propagate = False
