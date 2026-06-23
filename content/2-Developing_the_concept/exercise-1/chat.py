"""Show Setup Workflow — Section 2, Exercise 1.

A CLI conversation that interviews you about your podcast show, then writes
output/show_context.md and seeds all output/agents/*.md files.

Run:
    python content/2-Developing_the_concept/exercise/chat.py

Flow:
  1. Show Concept Agent asks one question at a time.
  2. You respond freely in the terminal.
  3. Type CONFIRM (case-insensitive) when you are happy with the concept.
  4. The agent emits structured JSON; the script writes your config files.
  5. Cycle guard: max 30 turns before forced CONFIRM.
"""

import asyncio
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# ── Path & env setup ──────────────────────────────────────────────────────────

WORKSPACE = Path(__file__).resolve().parents[3]
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))


from utils import load_env, create_agent, AgentOptions
load_env() 

# ── Paths ─────────────────────────────────────────────────────────────────────

RESOURCES_DIR   = Path(__file__).parent / "resources"
VOICE_SAMPLES   = RESOURCES_DIR / "voice-samples"
AGENT_TEMPLATES = RESOURCES_DIR / "agents"
AGENTS_DIR      = WORKSPACE / "output" / "agents"
OUTPUT_DIR      = WORKSPACE / "output"

MAX_TURNS = 30

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


# ── Voice tool ────────────────────────────────────────────────────────────────

# VibeVoice 7B: static metadata matched against actual sample files
_VIBEVOICE_META = {
    "Alice": {
        "gender": "female",
        "description": "Warm, conversational, approachable. Natural pacing, clear enunciation.",
        "best_for": "Curious hosts, friendly interviewers, accessible explainers",
        "sample": "en-Alice_woman.wav",
    },
    "Carter": {
        "gender": "male",
        "description": "Authoritative, confident, measured. Professional without being stiff.",
        "best_for": "Expert analysts, lead hosts, authoritative commentators",
        "sample": "en-Carter_man.wav",
    },
    "Frank": {
        "gender": "male",
        "description": "Casual, laid-back, relatable. Sounds like a knowledgeable friend.",
        "best_for": "Skeptics, everyman co-hosts, comedic relief, devil's advocates",
        "sample": "en-Frank_man.wav",
    },
    "Maya": {
        "gender": "female",
        "description": "Expressive, energetic, dynamic. Wide emotional range.",
        "best_for": "Enthusiastic experts, high-energy hosts, passionate practitioners",
        "sample": "en-Maya_woman.wav",
    },
    "Mary": {
        "gender": "female",
        "description": "Rich, narrative tone with a subtle ambient texture (BGM baked in).",
        "best_for": "Storytellers, reflective hosts, documentary-style narration",
        "sample": "en-Mary_woman_bgm.wav",
    },
    "Samuel": {
        "gender": "male",
        "description": "Deep, measured, thoughtful. Carries gravitas naturally. Indian English accent.",
        "best_for": "Senior experts, philosophical perspectives, calm counterpoints",
        "sample": "in-Samuel_man.wav",
    },
}

# MAI-2: seven English prebuilt voices
# Source: https://learn.microsoft.com/en-us/azure/ai-services/speech-service/mai-voices#prebuilt-voices-1
_MAI2_META = {
    "en-AU-Ilsa:MAI-Voice-2": {
        "gender": "female",
        "short_name": "Ilsa",
        "description": "Australian English female. Full emotional range — natural accent with wide expressiveness.",
        "best_for": "Storytellers, opinionated hosts, shows with international flavour",
        "expressions": [
            "angry", "confused", "determined", "disgusted", "embarrassed",
            "excited", "fearful", "happy", "hopeful", "jealous", "joyful",
            "regretful", "relieved", "sad", "shouting", "softvoice", "surprised", "whispering",
        ],
    },
    "en-US-Ethan:MAI-Voice-2": {
        "gender": "male",
        "short_name": "Ethan",
        "description": "Conversational, approachable US male. Full emotional range.",
        "best_for": "Everyman perspective, skeptics, casual co-hosts, curious questioners",
        "expressions": [
            "angry", "confused", "determined", "disgusted", "embarrassed",
            "excited", "fearful", "happy", "hopeful", "jealous", "joyful",
            "regretful", "relieved", "sad", "shouting", "softvoice", "surprised", "whispering",
        ],
    },
    "en-US-Grant:MAI-Voice-2": {
        "gender": "male",
        "short_name": "Grant",
        "description": "Neutral, clear US male delivery. No expression styles — consistent, uncoloured tone.",
        "best_for": "Steady narrators, hosts who need clean neutral delivery without emotional colouring",
        "expressions": [],
    },
    "en-US-Harper:MAI-Voice-2": {
        "gender": "female",
        "short_name": "Harper",
        "description": "Warm, determined US female. Strong emotional range, slightly narrower than full set.",
        "best_for": "Lead hosts, warm interviewers, determined storytellers",
        "expressions": [
            "angry", "confused", "determined", "embarrassed", "excited",
            "happy", "hopeful", "joyful", "regretful", "relieved", "sad",
            "shouting", "softvoice", "whispering",
        ],
    },
    "en-US-Iris:MAI-Voice-2": {
        "gender": "female",
        "short_name": "Iris",
        "description": "Clear, natural US female delivery. No expression styles — clean neutral tone.",
        "best_for": "Steady narrators, hosts who need clean neutral delivery without emotional colouring",
        "expressions": [],
    },
    "en-US-Jasper:MAI-Voice-2": {
        "gender": "male",
        "short_name": "Jasper",
        "description": "Clear, composed US male delivery. No expression styles — consistent neutral tone.",
        "best_for": "Steady narrators, hosts who need clean neutral delivery without emotional colouring",
        "expressions": [],
    },
    "en-US-Olivia:MAI-Voice-2": {
        "gender": "female",
        "short_name": "Olivia",
        "description": "Expressive, dynamic US female. Full emotional range including subtler emotions.",
        "best_for": "Passionate experts, opinionated hosts, high-energy or dramatic moments",
        "expressions": [
            "angry", "confused", "determined", "disgusted", "embarrassed",
            "excited", "fearful", "happy", "hopeful", "jealous", "joyful",
            "regretful", "relieved", "sad", "shouting", "softvoice", "surprised", "whispering",
        ],
    },
}


def _gender_matches(voice_gender: str, preference: str) -> bool:
    import re as _re
    pref = preference.lower()
    words = set(_re.findall(r"[\w/-]+", pref))
    neutral = {"any", "no", "none", "neutral", "either", "they", "they/them",
               "non-binary", "nonbinary", "doesnt", "doesn't", "matter", "preference"}
    if words & neutral:
        return True
    male_words = {"male", "man", "men", "he", "he/him", "masculine"}
    female_words = {"female", "woman", "women", "she", "she/her", "feminine"}
    if words & male_words:
        return voice_gender == "male"
    if words & female_words:
        return voice_gender == "female"
    return True  # unrecognised preference → show all


def list_voice_options(gender_preference: str) -> str:
    """Return available VibeVoice 7B and MAI-2 voice options for a podcast host.

    Call this once per host after learning their personality. Use the returned
    descriptions and sample paths to pick the best-fit voice for each model,
    then present your suggestions to the user and ask them to go listen before
    confirming.

    Args:
        gender_preference: The gender preference for the host's voice. Accepts
            flexible input — e.g. "female", "male", "non-binary", "doesn't
            matter", "any", "she/her", "he/him", "they/them", etc. Non-binary
            and neutral preferences return the full list.
    """
    lines = [f"Voice options (gender preference: {gender_preference!r})\n"]

    # ── VibeVoice ─────────────────────────────────────────────────────────────
    lines.append("VIBEVOICE 7B")
    lines.append("=" * 50)
    vv_dir = VOICE_SAMPLES / "vibe-voice"
    shown_vv = 0
    for name, meta in _VIBEVOICE_META.items():
        if not _gender_matches(meta["gender"], gender_preference):
            continue
        sample_path = vv_dir / meta["sample"]
        path_str = (
            str(sample_path.relative_to(WORKSPACE))
            if sample_path.exists()
            else f"(sample not found — expected {meta['sample']})"
        )
        lines.append(
            f"\n• {name} ({meta['gender']})\n"
            f"  {meta['description']}\n"
            f"  Best for: {meta['best_for']}\n"
            f"  Sample:   {path_str}"
        )
        shown_vv += 1

    if shown_vv == 0:
        lines.append("  (no voices match that gender preference)")

    # ── MAI-2 ─────────────────────────────────────────────────────────────────
    lines.append("\nMAI-2")
    lines.append("=" * 50)
    shown_mai2 = 0
    for voice_id, meta in _MAI2_META.items():
        if not _gender_matches(meta["gender"], gender_preference):
            continue
        sample_dir = VOICE_SAMPLES / "mai-2" / meta["short_name"]
        if sample_dir.exists():
            samples = sorted(sample_dir.glob("*.mp3"))
            sample_str = (
                str(sample_dir.relative_to(WORKSPACE)) + "/ ("
                + ", ".join(s.stem for s in samples) + ")"
                if samples else str(sample_dir.relative_to(WORKSPACE)) + "/ (no files yet)"
            )
        else:
            sample_str = "(run generate_mai2_samples.py to create samples)"

        lines.append(
            f"\n• {voice_id} ({meta['gender']})\n"
            f"  {meta['description']}\n"
            f"  Best for: {meta['best_for']}\n"
            f"  Expressions: {', '.join(meta['expressions'])}\n"
            f"  Samples: {sample_str}"
        )
        shown_mai2 += 1

    if shown_mai2 == 0:
        lines.append("  (no voices match that gender preference)")

    lines.append(
        "\nFull guide: content/2-Developing_the_concept/exercise/"
        "resources/voice-samples/voice-samples-guide.md"
    )

    return "\n".join(lines)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _bullet_list(items: list[str], fallback: str = "(none specified)") -> str:
    return "\n".join(f"- {i}" for i in items) if items else f"- {fallback}"


def _host_slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def parse_show_config(text: str) -> ShowConfig:
    """Extract the JSON block from the agent's response and parse it."""
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
    """Render the show_context.md content from a ShowConfig."""
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


def _build_host_agent(cfg: ShowConfig, host: HostConfig, template_name: str = "host.md") -> str:
    """Generate a fully fleshed-out host agent file from the template."""
    template = (AGENT_TEMPLATES / template_name).read_text()
    return (
        template
        .replace("{{HOST_NAME}}", host.name)
        .replace("{{HOST_PERSONA}}", host.persona)
        .replace("{{HOST_NICHE}}", host.niche)
        .replace("{{HOST_BACKGROUND}}", host.background or "(not specified)")
        .replace("{{HOST_OPINIONS}}", _bullet_list(host.opinions))
        .replace("{{HOST_QUIRKS}}", _bullet_list(host.quirks))
        .replace("{{HOST_CATCHPHRASES}}", _bullet_list(host.catchphrases))
    )


def seed_agent_files(cfg: ShowConfig) -> list[str]:
    """Copy agent templates from resources/ to output/agents/, prepending a show header.

    host.md is handled specially: one personalised file is generated per host
    (host-{slug}.md) instead of copying the generic template.
    """
    AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    written = []

    show_header = (
        f"_This agent serves the **{cfg.show_name}** podcast. "
        f"Show details are in `output/show_context.md`._\n\n"
    )

    for src in sorted(AGENT_TEMPLATES.glob("*.md")):
        if src.name == "host.md":
            continue
        dest = AGENTS_DIR / src.name
        dest.write_text(show_header + src.read_text())
        written.append(str(dest.relative_to(WORKSPACE)))

    for host in cfg.hosts:
        slug = _host_slug(host.name)
        dest = AGENTS_DIR / f"host-{slug}.md"
        dest.write_text(show_header + _build_host_agent(cfg, host))
        written.append(str(dest.relative_to(WORKSPACE)))

        recording_dest = AGENTS_DIR / f"host-{slug}-recording.md"
        recording_dest.write_text(show_header + _build_host_agent(cfg, host, "recording-host.md"))
        written.append(str(recording_dest.relative_to(WORKSPACE)))

    return written


def save_config(cfg: ShowConfig) -> tuple[Path, list[str]]:
    """Write show_context.md and seed agent files. Returns (context_path, agent_paths)."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ctx_path = OUTPUT_DIR / "show_context.md"
    ctx_path.write_text(build_show_context(cfg))
    agent_paths = seed_agent_files(cfg)
    return ctx_path, agent_paths


# ── CLI conversation loop ─────────────────────────────────────────────────────

DIVIDER = "─" * 60


async def stream_response(agent, message: str, session) -> str:
    """Send a message, stream the response to stdout, and return the full text."""
    print(f"\n\033[1;36mAgent:\033[0m ", end="", flush=True)
    stream = agent.run(message, session=session, stream=True)
    full_text = ""
    async for update in stream:
        chunk = update.text or ""
        print(chunk, end="", flush=True)
        full_text += chunk
    print()
    return full_text


async def main() -> None:
    print(DIVIDER)
    print("  Show Setup — Section 2, Exercise 1")
    print("  Type your answers below. Type CONFIRM when done.")
    print(DIVIDER)

    agent_def = (Path(__file__).parent / "show-concept-agent.md").read_text()
    agent = create_agent(AgentOptions(
        name="ShowConceptAgent",
        instructions=agent_def,
        tools=[list_voice_options],
    ))
    session = agent.create_session()

    await stream_response(
        agent,
        "Please start the show setup interview. Introduce yourself briefly and ask your first question.",
        session,
    )

    turn = 0
    while turn < MAX_TURNS:
        try:
            user_input = input(f"\n\033[1;33mYou:\033[0m ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\nInterrupted. Exiting without saving.")
            return

        if not user_input:
            continue

        turn += 1

        if user_input.upper() == "CONFIRM" or turn >= MAX_TURNS:
            if turn >= MAX_TURNS and user_input.upper() != "CONFIRM":
                print(f"\n[Reached {MAX_TURNS}-turn limit — finalising automatically.]")

            print(f"\n{DIVIDER}")
            print("  Generating your show configuration…")
            print(DIVIDER)

            json_text = await stream_response(
                agent,
                "The user has confirmed they are happy with the show concept. "
                "Output the final show configuration as a single JSON object in a "
                "```json fenced block, following the schema in your instructions. "
                "No surrounding text.",
                session,
            )

            for attempt in range(3):
                try:
                    cfg = parse_show_config(json_text)
                    break
                except (json.JSONDecodeError, KeyError) as e:
                    if attempt == 2:
                        print(f"\nCould not parse JSON after 3 attempts: {e}")
                        print("Raw output:\n", json_text)
                        return
                    print(f"\n[JSON parse error: {e} — asking agent to retry…]")
                    json_text = await stream_response(
                        agent,
                        f"The JSON could not be parsed ({e}). Please output ONLY a single "
                        "```json block with the show configuration and nothing else.",
                        session,
                    )

            ctx_path, agent_paths = save_config(cfg)

            print(f"\n{DIVIDER}")
            print(f"  Show configured: {cfg.show_name}")
            print(f"  Hosts: {', '.join(h.name for h in cfg.hosts)}")
            print()
            print("  Files written:")
            print(f"    {ctx_path.relative_to(WORKSPACE)}")
            for p in agent_paths:
                print(f"    {p}")
            print(DIVIDER)
            print()
            print("Next steps:")
            print("  1. Open output/agents/ and read the agent definitions.")
            print("  2. Edit any .md file — your changes feed directly into Section 3.")
            print("  3. Run the Episode Production Workflow (Section 3).")
            return

        await stream_response(agent, user_input, session)


if __name__ == "__main__":
    asyncio.run(main())
