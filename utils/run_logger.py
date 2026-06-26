"""Per-run logging utilities shared across podcast production workflows."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path

from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult


class WorkflowRunLogger:
    """Manages per-run file logging and artifact storage for a workflow.

    Usage:
        run_logger = WorkflowRunLogger(__name__)
        run_logger.start(WORKSPACE, "script", brief)
        run_logger.log_artifact("research.md", content)
        run_logger.info("phase complete")
        exporter = run_logger.create_span_exporter()
    """

    def __init__(self, logger_name: str):
        self._logger = logging.getLogger(logger_name)
        self._file_handler: logging.FileHandler | None = None
        self.run_id: str = ""
        self.run_log_dir: Path | None = None

    def start(self, workspace: Path, runs_subdir: str, brief: str, run_dir: Path | None = None) -> None:
        """Create a per-run log directory and attach a FileHandler for this run."""
        self.run_id = str(uuid.uuid4())
        if run_dir is not None:
            self.run_log_dir = run_dir
        else:
            self.run_log_dir = workspace / "output" / "workflow-runs" / runs_subdir / self.run_id
            (self.run_log_dir / "scripts").mkdir(parents=True, exist_ok=True)
        self.run_log_dir.mkdir(parents=True, exist_ok=True)

        if self._file_handler:
            logging.getLogger().removeHandler(self._file_handler)
            self._file_handler.close()

        log_file = self.run_log_dir / "run.log"
        self._file_handler = logging.FileHandler(log_file)
        self._file_handler.setLevel(logging.DEBUG)
        self._file_handler.setFormatter(
            logging.Formatter("%(asctime)s  %(name)-35s  %(levelname)s  %(message)s")
        )
        logging.getLogger().addHandler(self._file_handler)

        manifest = {
            "run_id": self.run_id,
            "started_at": datetime.now().isoformat(),
            "brief": brief,
        }
        (self.run_log_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
        self._logger.info("=== run %s started  brief=%r ===", self.run_id, brief)

    def log_artifact(self, filename: str, content: str) -> None:
        """Write a text artifact to the current run's log directory."""
        if self.run_log_dir and self.run_log_dir.exists():
            (self.run_log_dir / filename).write_text(content, encoding="utf-8")

    def info(self, *args, **kwargs) -> None:
        self._logger.info(*args, **kwargs)

    def warning(self, *args, **kwargs) -> None:
        self._logger.warning(*args, **kwargs)

    def create_span_exporter(self) -> "RunJsonlSpanExporter":
        """Return a span exporter that writes JSONL traces to this run's log dir."""
        return RunJsonlSpanExporter(self)


def find_latest_run_dir(workspace: Path, runs_subdir: str) -> Path | None:
    root = workspace / "output" / "workflow-runs" / runs_subdir
    if not root.exists() or not root.is_dir():
        return None
    run_dirs = [p for p in root.iterdir() if p.is_dir()]
    if not run_dirs:
        return None
    return max(run_dirs, key=lambda p: p.stat().st_mtime)


class RunJsonlSpanExporter(SpanExporter):
    """Exports OTel spans as JSONL to the active run's log directory.

    Registered once at startup; reads run_log_dir from the WorkflowRunLogger
    at export time so it automatically writes to the correct per-run directory.

    With enable_sensitive_data=True the framework attaches full message content
    (inputs AND outputs for every agent call) as span events, so the JSONL
    contains the complete reasoning trace for evaluation.
    """

    def __init__(self, run_logger: WorkflowRunLogger):
        self._run_logger = run_logger

    def export(self, spans) -> SpanExportResult:  # type: ignore[override]
        run_log_dir = self._run_logger.run_log_dir
        run_id = self._run_logger.run_id
        if not (run_log_dir and run_log_dir.exists()):
            return SpanExportResult.SUCCESS
        try:
            jsonl_path = run_log_dir / "traces.jsonl"
            with jsonl_path.open("a", encoding="utf-8") as f:
                for span in spans:
                    entry: dict = {
                        "run_id": run_id,
                        "name": span.name,
                        "trace_id": format(span.context.trace_id, "032x"),
                        "span_id": format(span.context.span_id, "016x"),
                        "parent_span_id": (
                            format(span.parent.span_id, "016x") if span.parent else None
                        ),
                        "start_ns": span.start_time,
                        "end_ns": span.end_time,
                        "attributes": dict(span.attributes) if span.attributes else {},
                        "events": [
                            {
                                "name": e.name,
                                "timestamp_ns": e.timestamp,
                                "attributes": dict(e.attributes) if e.attributes else {},
                            }
                            for e in (span.events or [])
                        ],
                        "status": (
                            span.status.status_code.name
                            if hasattr(span, "status")
                            else "OK"
                        ),
                    }
                    f.write(json.dumps(entry) + "\n")
        except Exception as exc:
            self._run_logger.warning("trace JSONL export failed: %s", exc)
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        pass


def summarize_token_usage_trace(trace_path: Path | str) -> dict[str, int]:
    """Summarize GenAI token usage from a traces.jsonl file."""
    trace_path = Path(trace_path)
    if not trace_path.exists() or not trace_path.is_file():
        return {}

    totals = {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "spans_with_usage": 0,
    }

    with trace_path.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            attributes = entry.get("attributes", {}) or {}
            input_tokens = attributes.get("gen_ai.usage.input_tokens")
            output_tokens = attributes.get("gen_ai.usage.output_tokens")
            if input_tokens is not None or output_tokens is not None:
                totals["spans_with_usage"] += 1
            if isinstance(input_tokens, int):
                totals["input_tokens"] += input_tokens
            if isinstance(output_tokens, int):
                totals["output_tokens"] += output_tokens

    totals["total_tokens"] = totals["input_tokens"] + totals["output_tokens"]
    return totals
