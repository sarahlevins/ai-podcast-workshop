"""Render a writer/editor source script to VibeVoice or Azure SSML.

The Script Writer and Editor agents emit a single "source script" with
inline inflection cues. This module parses that source and renders to
the two target formats. See utils/script_format_vibevoice.md and
utils/script_format_azure_ssml.md for the full spec.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from xml.sax.saxutils import escape as xml_escape


DEFAULT_AZURE_VOICES: dict[str, str] = {
    "Ken":  "en-GB-Ada:DragonHDLatestNeural",
    "Maya": "en-GB-Ollie:DragonHDLatestNeural",
}

CLIP_WORD_LIMIT = 250  # ~1-2 min of spoken audio at podcast pace


# ── Source parsing ────────────────────────────────────────────────────────────

@dataclass
class Section:
    name: str


@dataclass
class Turn:
    host: str
    text: str  # raw, still contains inline cues


_SECTION_RE = re.compile(r"^\[(.+)\]\s*$")
_TURN_RE    = re.compile(r"^([A-Za-z][A-Za-z0-9 _'-]*):\s*(.+)$")
_NOTES_RE   = re.compile(r"^\[Editor", re.IGNORECASE)


def parse_source(script: str) -> list[Section | Turn]:
    """Parse a source script into a list of Sections and Turns.

    Stops at the first '[Editor...' marker. Skips blank and unparseable lines.
    """
    items: list[Section | Turn] = []
    for line in script.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if _NOTES_RE.match(stripped):
            break
        if m := _SECTION_RE.match(stripped):
            items.append(Section(name=m.group(1).strip()))
            continue
        if m := _TURN_RE.match(stripped):
            items.append(Turn(host=m.group(1).strip(), text=m.group(2).strip()))
    return items


# ── Inline cue stripping (for VibeVoice) ──────────────────────────────────────

_STRIP_PATTERNS = [
    re.compile(r"\[lang:[^\]]+\]"),
    re.compile(r"\[/lang\]"),
    re.compile(r"\[sfx:[^\]]+\]"),
    re.compile(r"\[[a-zA-Z][a-zA-Z0-9_-]*\]"),
    re.compile(r"\(pause(?::\d+m?s)?\)"),
    re.compile(r"\(rate:[a-zA-Z+\-0-9%.]+\)"),
    re.compile(r"\(volume:[a-zA-Z+\-0-9%.]+\)"),
]


def _strip_cues(text: str) -> str:
    for pat in _STRIP_PATTERNS:
        text = pat.sub("", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"\1", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


# ── Renderer: VibeVoice ───────────────────────────────────────────────────────

def render_vibevoice(items: list[Section | Turn]) -> str:
    """Plain-text VibeVoice output. Emits 'speaker N: text' lines."""
    speaker_index: dict[str, int] = {}
    lines: list[str] = []
    for item in items:
        if isinstance(item, Turn):
            text = _strip_cues(item.text)
            if text:
                if item.host not in speaker_index:
                    speaker_index[item.host] = len(speaker_index) + 1
                n = speaker_index[item.host]
                lines.append(f"speaker {n}: {text}")
    return "\n".join(lines)


# ── Renderer: Azure SSML ──────────────────────────────────────────────────────

_INLINE_RE = re.compile(
    r"""
    (?P<lang_open>\[lang:(?P<lang>[a-zA-Z-]+)\])             |
    (?P<lang_close>\[/lang\])                                |
    (?P<sfx>\[sfx:(?P<sfx_url>[^\]]+)\])                     |
    (?P<style>\[(?P<style_name>[a-zA-Z][a-zA-Z0-9_-]*)\])    |
    (?P<pause>\(pause(?::(?P<pause_ms>\d+)m?s)?\))           |
    (?P<rate>\(rate:(?P<rate_val>[a-zA-Z+\-0-9%.]+)\))       |
    (?P<volume>\(volume:(?P<volume_val>[a-zA-Z+\-0-9%.]+)\)) |
    (?P<emph>\*\*(?P<emph_text>[^*]+)\*\*)
    """,
    re.VERBOSE,
)


def _render_turn_ssml(text: str) -> str:
    """Render one turn body to SSML (without the surrounding <voice>)."""
    out: list[str] = []
    cur_style: str | None = None
    cur_rate: str | None = None
    cur_volume: str | None = None
    in_lang: str | None = None
    open_now = False

    def open_wrap() -> str:
        s = ""
        if cur_style:
            s += f'<mstts:express-as style="{xml_escape(cur_style)}">'
        attrs = []
        if cur_rate:   attrs.append(f'rate="{xml_escape(cur_rate)}"')
        if cur_volume: attrs.append(f'volume="{xml_escape(cur_volume)}"')
        if attrs:
            s += f"<prosody {' '.join(attrs)}>"
        return s

    def close_wrap() -> str:
        s = ""
        if cur_rate or cur_volume:
            s += "</prosody>"
        if cur_style:
            s += "</mstts:express-as>"
        return s

    def ensure_open():
        nonlocal open_now
        if not open_now and (cur_style or cur_rate or cur_volume):
            out.append(open_wrap())
            open_now = True

    def ensure_closed():
        nonlocal open_now
        if open_now:
            out.append(close_wrap())
            open_now = False

    def emit_text(s: str) -> None:
        s = s.strip()
        if not s:
            return
        ensure_open()
        if in_lang:
            out.append(f'<lang xml:lang="{xml_escape(in_lang)}">{xml_escape(s)}</lang>')
        else:
            out.append(xml_escape(s))

    pos = 0
    for m in _INLINE_RE.finditer(text):
        if m.start() > pos:
            emit_text(text[pos:m.start()])
        pos = m.end()

        if m.group("style"):
            ensure_closed()
            cur_style = m.group("style_name")
        elif m.group("rate"):
            ensure_closed()
            cur_rate = m.group("rate_val")
        elif m.group("volume"):
            ensure_closed()
            cur_volume = m.group("volume_val")
        elif m.group("pause"):
            ms = m.group("pause_ms")
            tag = f'<break time="{ms}ms"/>' if ms else '<break strength="medium"/>'
            ensure_open()
            out.append(tag)
        elif m.group("emph"):
            ensure_open()
            out.append(f'<emphasis level="strong">{xml_escape(m.group("emph_text"))}</emphasis>')
        elif m.group("sfx"):
            ensure_closed()
            out.append(f'<audio src="{xml_escape(m.group("sfx_url"))}">(audio)</audio>')
        elif m.group("lang_open"):
            in_lang = m.group("lang")
        elif m.group("lang_close"):
            in_lang = None

    if pos < len(text):
        emit_text(text[pos:])
    ensure_closed()
    return "".join(out).strip()


def render_ssml(
    items: list[Section | Turn],
    voices: dict[str, str] | None = None,
    default_voice: str = "en-GB-Ollie:DragonHDLatestNeural",
) -> str:
    """Render to a complete Azure SSML document. Unknown hosts fall back to
    `default_voice`."""
    voice_map = voices or DEFAULT_AZURE_VOICES
    parts: list[str] = [
        '<speak version="1.0" '
        'xmlns="http://www.w3.org/2001/10/synthesis" '
        'xmlns:mstts="https://www.w3.org/2001/mstts" '
        'xml:lang="en-GB">'
    ]
    for item in items:
        if isinstance(item, Section):
            parts.append(f"  <!-- {xml_escape(item.name)} -->")
        else:
            voice = voice_map.get(item.host, default_voice)
            body = _render_turn_ssml(item.text)
            if body:
                parts.append(f'  <voice name="{xml_escape(voice)}">{body}</voice>')
    parts.append("</speak>")
    return "\n".join(parts)


# ── Clipping: 1-2 minute preview ──────────────────────────────────────────────

def clip_source(script: str, word_limit: int = CLIP_WORD_LIMIT) -> str:
    """Return a clipped version of the source script.

    Preserves section headers and whole turns. Stops at the end of the turn
    that pushes the cumulative spoken-word count over `word_limit`.
    """
    out: list[str] = []
    spoken_words = 0
    for line in script.splitlines():
        stripped = line.strip()
        if not stripped:
            out.append(line)
            continue
        if _NOTES_RE.match(stripped):
            break
        if _SECTION_RE.match(stripped):
            out.append(line)
            continue
        if m := _TURN_RE.match(stripped):
            out.append(line)
            spoken_words += len(_strip_cues(m.group(2)).split())
            if spoken_words >= word_limit:
                break
        else:
            out.append(line)
    return "\n".join(out).rstrip() + "\n"
