from __future__ import annotations

import logging
import os
from pathlib import Path

from opentelemetry import metrics, trace
from opentelemetry.sdk.resources import Resource

# Traces
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor, SpanExporter, SpanExportResult
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

# Metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    MetricExporter,
    MetricExportResult,
    MetricsData,
    PeriodicExportingMetricReader,
)
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter

# Logs
from opentelemetry._logs import set_logger_provider
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler, ReadableLogRecord
from opentelemetry.sdk._logs.export import (
    BatchLogRecordProcessor,
    LogRecordExportResult,
    LogRecordExporter,
)
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter

SERVICE_NAME = "pizza-otel-demo"
_DEFAULT_COLLECTOR_ENDPOINT = "http://localhost:4317"
OTEL_COLLECTOR_ENDPOINT = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", _DEFAULT_COLLECTOR_ENDPOINT)
_DEFAULT_EXPORT_TARGET = "otlp"
_DEFAULT_LOCAL_EXPORT_DIR = "telemetry_output"


def _append_line(file_path: Path, line: str) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("a", encoding="utf-8") as output_file:
        output_file.write(line)
        output_file.write("\n")


class JsonLineSpanExporter(SpanExporter):
    def __init__(self, file_path: Path) -> None:
        self._file_path = file_path

    def export(self, spans) -> SpanExportResult:
        for span in spans:
            _append_line(self._file_path, span.to_json())
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        return None

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True


class JsonLineLogExporter(LogRecordExporter):
    def __init__(self, file_path: Path) -> None:
        super().__init__()
        self._file_path = file_path

    def export(self, batch: list[ReadableLogRecord]) -> LogRecordExportResult:
        for log_record in batch:
            _append_line(self._file_path, log_record.to_json())
        return LogRecordExportResult.SUCCESS

    def shutdown(self) -> None:
        return None


class JsonMetricsExporter(MetricExporter):
    def __init__(self, file_path: Path, **kwargs) -> None:
        super().__init__(**kwargs)
        self._file_path = file_path

    def export(self, metrics_data: MetricsData, timeout_millis: float = 10000, **kwargs) -> MetricExportResult:
        _append_line(self._file_path, metrics_data.to_json())
        return MetricExportResult.SUCCESS

    def shutdown(self, timeout_millis: float = 30000, **kwargs) -> None:
        return None

    def force_flush(self, timeout_millis: float = 10000) -> bool:
        return True


def configure_otel() -> None:
    resource = Resource.create({"service.name": SERVICE_NAME})
    running_under_pytest = "PYTEST_CURRENT_TEST" in os.environ
    export_target = os.environ.get("OTEL_EXPORT_TARGET", _DEFAULT_EXPORT_TARGET).strip().lower()
    local_export_dir = Path(os.environ.get("OTEL_LOCAL_EXPORT_DIR", _DEFAULT_LOCAL_EXPORT_DIR)).expanduser()
    traces_file = local_export_dir / "traces.jsonl"
    metrics_file = local_export_dir / "metrics.jsonl"
    logs_file = local_export_dir / "logs.jsonl"

    # Trace provider
    tracer_provider = TracerProvider(resource=resource)
    if not running_under_pytest:
        if export_target == "file":
            tracer_provider.add_span_processor(SimpleSpanProcessor(JsonLineSpanExporter(traces_file)))
        else:
            tracer_provider.add_span_processor(
                BatchSpanProcessor(OTLPSpanExporter(endpoint=OTEL_COLLECTOR_ENDPOINT))
            )
    trace.set_tracer_provider(tracer_provider)

    # Meter provider
    metric_readers = []
    if not running_under_pytest:
        if export_target == "file":
            metric_readers.append(
                PeriodicExportingMetricReader(
                    JsonMetricsExporter(metrics_file),
                    export_interval_millis=2000,
                )
            )
        else:
            metric_readers.append(
                PeriodicExportingMetricReader(
                    OTLPMetricExporter(endpoint=OTEL_COLLECTOR_ENDPOINT),
                    export_interval_millis=5000,
                )
            )
    meter_provider = MeterProvider(
        resource=resource,
        metric_readers=metric_readers,
    )
    metrics.set_meter_provider(meter_provider)

    # Log provider
    logger_provider = LoggerProvider(resource=resource)
    if not running_under_pytest:
        if export_target == "file":
            logger_provider.add_log_record_processor(BatchLogRecordProcessor(JsonLineLogExporter(logs_file)))
        else:
            logger_provider.add_log_record_processor(
                BatchLogRecordProcessor(OTLPLogExporter(endpoint=OTEL_COLLECTOR_ENDPOINT))
            )
    set_logger_provider(logger_provider)

    handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)
    app_logger = logging.getLogger("pizza_api")
    app_logger.setLevel(logging.INFO)
    app_logger.handlers.clear()
    app_logger.addHandler(handler)
    app_logger.propagate = False

    if not running_under_pytest and export_target == "file":
        app_logger.info(
            "OpenTelemetry export configured for local files",
            extra={"telemetry_dir": str(local_export_dir.resolve())},
        )
