"""Shared pipeline state, types, and helpers for all executor modules."""

import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

# ── Path & env setup ──────────────────────────────────────────────────────────

WORKSPACE = Path(__file__).resolve().parents[4]
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(WORKSPACE / ".env")

from utils.run_logger import WorkflowRunLogger  # noqa: E402

# ── Show context ──────────────────────────────────────────────────────────────

SHOW_CONTEXT_PATH = WORKSPACE / "output" / "show_context.md"

# ── Shared pipeline state ─────────────────────────────────────────────────────

@dataclass
class PipelineState:
    brief: str = ""
    slug: str = ""
    episode_dir: Path = field(default_factory=Path)
    cli_brief: str = ""

    # Research accumulation
    research_results: list[str] = field(default_factory=list)
    research_needed: int = 0

    # Scripting loop
    script: str = ""
    script_cycle: int = 0
    MAX_SCRIPT_CYCLES: int = 3

    # Producer loop
    producer_cycle: int = 0
    MAX_PRODUCER_CYCLES: int = 2

    # HITL
    hitl_rounds: int = 0
    MAX_HITL_ROUNDS: int = 3

    # Content pipeline accumulation
    content_results: dict[str, str] = field(default_factory=dict)
    content_needed: int = 3   # show notes + metadata + promo


_state = PipelineState()

# ── Per-run logging ───────────────────────────────────────────────────────────

_run_logger = WorkflowRunLogger("workflow")
_JSONL_SPAN_EXPORTER = _run_logger.create_span_exporter()


def _start_run_logging() -> None:
    _run_logger.start(WORKSPACE, "script", _state.brief, run_dir=_state.episode_dir / "recording-artifacts")


def _log_artifact(filename: str, content: str) -> None:
    _run_logger.log_artifact(filename, content)


# ── Workflow input type ───────────────────────────────────────────────────────

@dataclass
class EpisodeBriefInput:
    brief: str = ""
    """What should this episode be about? e.g. 'the numbers and what they mean'"""


# ── Human-in-the-loop request types ──────────────────────────────────────────

@dataclass
class ScriptReviewRequest:
    script: str
    round: int
    prompt: str = (
        "Review the script.\n"
        "  • Type 'ACCEPT' to approve it and move to the content pipeline.\n"
        "  • Or describe what you want changed (max 3 rounds)."
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_episode_dir(brief: str) -> Path:
    slug = re.sub(r"[^a-z0-9]+", "-", brief.lower().strip())[:50].strip("-")
    today = date.today().isoformat()
    ep_dir = WORKSPACE / "output" / "episodes" / f"{today}-{slug}"
    (ep_dir / "recording-artifacts").mkdir(parents=True, exist_ok=True)
    return ep_dir


def editor_approved(editor_text: str) -> bool:
    """Returns True if the Editor's response contains APPROVED."""
    return bool(re.search(r"\bAPPROVED\b", editor_text, re.IGNORECASE))


def producer_approved(producer_text: str) -> bool:
    """Returns True if the Producer's response signals approval."""
    return bool(re.search(r"\bAPPROVED\b", producer_text, re.IGNORECASE))


def append_episode_history(brief: str, script: str) -> None:
    """Append a brief episode history entry to show_context.md."""
    today = date.today().isoformat()
    entry = f"\n### {today} — {brief[:60]}\n- **Topic / Angle:** {brief}\n"
    with open(SHOW_CONTEXT_PATH, "a") as f:
        f.write(entry)
