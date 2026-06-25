"""Data model and file-writing helpers for the show setup workflow."""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

WORKSPACE  = Path(__file__).resolve().parents[4]
AGENTS_DIR = WORKSPACE / "output" / "agents"
OUTPUT_DIR = WORKSPACE / "output"

# ── Data types ────────────────────────────────────────────────────────────────

@dataclass
class HostConfig:
    name: str
    persona: str
    niche: str
    vibevoice: str
    mai2: str
    background: str = ""
    opinions: list[str] = field(default_factory=list)
    quirks: list[str] = field(default_factory=list)
    catchphrases: list[str] = field(default_factory=list)


@dataclass
class ShowConfig:
    show_name: str
    tagline: str
    format: str
    audience: str
    tone: str
    brand_voice: str
    segments: list[str]
    hosts: list[HostConfig]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _bullet_list(items: list[str], fallback: str = "(none specified)") -> str:
    return "\n".join(f"- {i}" for i in items) if items else f"- {fallback}"


def _host_slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def parse_show_config(text: str) -> ShowConfig:
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    raw = match.group(1) if match else text
    data = json.loads(raw)
    hosts = [
        HostConfig(
            name=h["name"],
            persona=h["persona"],
            niche=h["niche"],
            vibevoice=h.get("vibevoice", ""),
            mai2=h.get("mai2", ""),
            background=h.get("background", ""),
            opinions=h.get("opinions", []),
            quirks=h.get("quirks", []),
            catchphrases=h.get("catchphrases", []),
        )
        for h in data["hosts"]
    ]
    return ShowConfig(
        show_name=data["show_name"],
        tagline=data["tagline"],
        format=data["format"],
        audience=data["audience"],
        tone=data["tone"],
        brand_voice=data["brand_voice"],
        segments=data["segments"],
        hosts=hosts,
    )


def _host_context_block(h: HostConfig) -> str:
    return (
        f"### {h.name}\n"
        f"- **Persona:** {h.persona}\n"
        f"- **Niche:** {h.niche}\n"
        f"- **Background:** {h.background}\n"
        f"- **Opinions:**\n{_bullet_list(h.opinions)}\n"
        f"- **Quirks:**\n{_bullet_list(h.quirks)}\n"
        f"- **Catchphrases:**\n{_bullet_list(h.catchphrases)}\n"
        f"- **Voice IDs:**\n"
        f"  - vibevoice: {h.vibevoice}\n"
        f"  - mai2: {h.mai2}\n"
    )


def build_show_context(cfg: ShowConfig) -> str:
    hosts_section = "\n".join(_host_context_block(h) for h in cfg.hosts)
    segments_list = "\n".join(f"- {s}" for s in cfg.segments)
    return (
        f"# Show Context: {cfg.show_name}\n"
        f"\n"
        f"## Identity\n"
        f"- **Name / Tagline:** {cfg.show_name} — {cfg.tagline}\n"
        f"- **Format:** {cfg.format}\n"
        f"- **Target audience:** {cfg.audience}\n"
        f"- **Tone:** {cfg.tone}\n"
        f"- **Brand voice notes:** {cfg.brand_voice}\n"
        f"\n"
        f"## Recurring Segments\n"
        f"{segments_list}\n"
        f"\n"
        f"## Hosts\n"
        f"\n"
        f"{hosts_section.rstrip()}\n"
        f"\n"
        f"## Episode History\n"
        f"\n"
        f"(Appended after each episode — lets agents avoid topic repetition and build callbacks)\n"
    )


def _build_host_identity(host: HostConfig) -> str:
    return (
        f"# Host: {host.name}\n\n"
        f"You are **{host.name}**. Everything below defines who you are — stay in character throughout.\n\n"
        f"## Who you are\n\n"
        f"**Persona:** {host.persona}\n\n"
        f"**Niche:** {host.niche}\n\n"
        f"**Background:** {host.background or '(not specified)'}\n\n"
        f"**Your opinions:**\n{_bullet_list(host.opinions)}\n\n"
        f"**How you talk:**\n{_bullet_list(host.quirks)}\n\n"
        f"**Your catchphrases:**\n{_bullet_list(host.catchphrases)}\n"
    )


def seed_agent_files(cfg: ShowConfig) -> list[str]:
    AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    show_header = (
        f"_This agent serves the **{cfg.show_name}** podcast. "
        f"Show details are in `output/show_context.md`._\n\n"
    )
    written = []
    for host in cfg.hosts:
        dest = AGENTS_DIR / f"host-{_host_slug(host.name)}.md"
        dest.write_text(show_header + _build_host_identity(host))
        written.append(str(dest.relative_to(WORKSPACE)))
    return written


def save_config(cfg: ShowConfig) -> tuple[Path, list[str]]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ctx_path = OUTPUT_DIR / "show_context.md"
    ctx_path.write_text(build_show_context(cfg))
    return ctx_path, seed_agent_files(cfg)
