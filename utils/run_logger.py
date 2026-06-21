"""Per-run logging utilities shared across podcast production workflows."""

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

    def start(self, workspace: Path, runs_subdir: str, brief: str) -> None:
        """Create a per-run log directory and attach a FileHandler for this run."""
        self.run_id = str(uuid.uuid4())
        self.run_log_dir = workspace / "output" / "workflow-runs" / runs_subdir / self.run_id
        self.run_log_dir.mkdir(parents=True, exist_ok=True)
        (self.run_log_dir / "scripts").mkdir(exist_ok=True)

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
