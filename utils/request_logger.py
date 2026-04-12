"""
utils/request_logger.py
CONCEPT: Production ML Monitoring

WHY THIS MATTERS:
In production ML systems, you MUST track:
- Latency per model call (SLA compliance)
- Token usage (cost control)
- Error rates (reliability)
- Model performance over time (drift detection)

This is called MLOps (ML Operations).
Every ML Engineer interview will ask about this.

We store logs in memory (for demo). In production:
- Use Prometheus + Grafana for metrics
- Use Datadog or New Relic for APM
- Use MLflow or Weights & Biases for model tracking
"""
import time
import logging
from datetime import datetime
from typing import Optional
from collections import deque

logger = logging.getLogger(__name__)

# In-memory circular buffer — stores last 1000 requests
# In production: push to a time-series database
_request_log = deque(maxlen=1000)


def log_request(
    endpoint: str,
    model: str,
    latency_ms: float,
    success: bool,
    tokens_used: Optional[int] = None,
    user_id: Optional[int] = None,
    extra: Optional[dict] = None
):
    """Log a model API call with timing and metadata."""
    entry = {
        "timestamp":   datetime.utcnow().isoformat(),
        "endpoint":    endpoint,
        "model":       model,
        "latency_ms":  round(latency_ms, 1),
        "success":     success,
        "tokens_used": tokens_used,
        "user_id":     user_id,
        **(extra or {}),
    }
    _request_log.append(entry)

    level = logging.WARNING if latency_ms > 5000 else logging.INFO
    logger.log(level,
        f"[{endpoint}] model={model} latency={latency_ms:.0f}ms "
        f"success={success} tokens={tokens_used}"
    )


def get_stats() -> dict:
    """Aggregate stats over all logged requests."""
    if not _request_log:
        return {"total_requests": 0}

    logs = list(_request_log)
    latencies    = [l["latency_ms"] for l in logs if l["success"]]
    error_count  = sum(1 for l in logs if not l["success"])
    model_counts = {}
    endpoint_counts = {}

    for l in logs:
        model_counts[l["model"]]       = model_counts.get(l["model"], 0) + 1
        endpoint_counts[l["endpoint"]] = endpoint_counts.get(l["endpoint"], 0) + 1

    return {
        "total_requests":    len(logs),
        "success_rate":      round((len(logs) - error_count) / len(logs) * 100, 1),
        "error_count":       error_count,
        "avg_latency_ms":    round(sum(latencies) / len(latencies), 1) if latencies else 0,
        "p95_latency_ms":    round(sorted(latencies)[int(len(latencies) * 0.95)], 1) if latencies else 0,
        "max_latency_ms":    round(max(latencies), 1) if latencies else 0,
        "model_usage":       model_counts,
        "endpoint_usage":    endpoint_counts,
        "recent_requests":   logs[-10:][::-1],  # last 10, newest first
    }


class Timer:
    """Context manager for timing code blocks."""
    def __init__(self):
        self.elapsed_ms = 0.0

    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, *args):
        self.elapsed_ms = (time.perf_counter() - self._start) * 1000