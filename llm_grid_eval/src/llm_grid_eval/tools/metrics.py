"""Tool: metrics - return current experiment metrics."""

from __future__ import annotations

from ..services.metrics_collector import MetricsCollector


def metrics(collector: MetricsCollector) -> dict:
    return collector.get_metrics()

