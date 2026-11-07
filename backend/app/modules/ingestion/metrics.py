from __future__ import annotations

from prometheus_client import Counter, Histogram

IMPORT_RUNS = Counter(
    "import_runs_total", "Dataset import runs by final status", ["status", "dry_run"]
)
IMPORT_ROWS = Counter(
    "import_rows_total", "Source rows processed by entity and outcome", ["entity", "outcome"]
)
IMPORT_DURATION = Histogram(
    "import_duration_seconds",
    "Wall time of dataset imports",
    buckets=(0.5, 1, 2, 5, 10, 30, 60, 120, 300),
)
