"""Audio Production Workflow — Section 4.

Takes a transcript.json produced by Section 3 and produces a final podcast
audio preview, with music and SFX.

Run:
    python content/4-Engineering_the_audio/exercise-5/workflow.py \
        --episode <episode-slug-or-name> \
        --model <mai-2|vibe-voice>

If --episode is omitted the most-recent episode directory is used.
If --model is omitted the workflow asks the user on startup.

Phases:
  1. Load transcript  — validate & read transcript.json from episode dir
  1a. Voice generator (parallel) — SSML (mai-2) or VibeVoice script + overlap manifest
  1b. Music Director  (parallel) — music & SFX plan JSON

  2. Audio generation (fork by model):
      mai-2      → MAI-2 API executor → single audio file
      vibe-voice → HITL: user runs locally → places file in episode dir

  3. Whisper        — transcribe the audio file to get word-level timestamps

  4. Audio Technician (fan-in: whisper + music plan)
                   → timestamped transcript JSON

  5. Audio Mixer   → ffmpeg command plan JSON
  5a. Mix Executor → runs ffmpeg commands → final episode_preview.mp3

Outputs (all within audio-artifacts/ inside the episode directory):
  scripts/mai2/script.xml            (mai-2 mode)
  scripts/vibevoice/script.txt       (vibe-voice mode)
  scripts/overlap-manifest.json
  scripts/music-plan.json
  speech/speech.mp3                  (generated audio — all utterances)
  whisper/whisper-transcript.txt
  mix/timestamped-transcript.json
  mix/mix-plan.json
  mix/transcript-with-files.json
  mix/clips/                         (per-utterance clips created by mixer)
  mix/episode_preview.mp3            (final output)
"""

import json
import logging
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

# ── Path & env setup ──────────────────────────────────────────────────────────

WORKSPACE = Path(__file__).resolve().parents[3]
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(WORKSPACE / ".env")

from agent_framework import (  # noqa: E402
    AgentExecutor,
    AgentExecutorRequest,
    AgentExecutorResponse,
    AgentResponse,
    Executor,
    Message,
    WorkflowBuilder,
    WorkflowContext,
    handler,
    response_handler,
)

from agents import (  # noqa: E402
    create_ssml_voice_generator,
    create_vibe_voice_generator,
    create_music_director,
    create_audio_technician,
    create_audio_mixer,
)

# ── Constants ─────────────────────────────────────────────────────────────────

SHOW_CONTEXT_PATH = WORKSPACE / "output" / "show_context.md"
EPISODES_DIR      = WORKSPACE / "output" / "episodes"
MAI2_SCRIPT       = WORKSPACE / "content" / "4-Engineering_the_audio" / "exercise-5" / "_resources" / "mai-2.py"

VALID_MODELS = {"mai-2", "vibe-voice"}

if not SHOW_CONTEXT_PATH.exists():
    raise FileNotFoundError(
        f"{SHOW_CONTEXT_PATH} not found.\n"
        "Run the Show Setup Workflow first."
    )

SHOW_CONTEXT = SHOW_CONTEXT_PATH.read_text()


# ── Episode directory lookup ──────────────────────────────────────────────────

def _find_episode_dir(slug: str | None) -> Path:
    if slug:
        candidates = list(EPISODES_DIR.glob(f"*{slug}*"))
        if not candidates:
            raise FileNotFoundError(
                f"No episode directory matching '{slug}' in {EPISODES_DIR}"
            )
        return sorted(candidates)[-1]

    dirs = [d for d in EPISODES_DIR.iterdir() if d.is_dir()]
    if not dirs:
        raise FileNotFoundError(
            f"No episode directories in {EPISODES_DIR}.\n"
            "Run the Episode Production Workflow (Section 3) first."
        )
    return sorted(dirs)[-1]


# ── Audio utilities ───────────────────────────────────────────────────────────

def _get_audio_duration(path: Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True,
    )
    return float(r.stdout.strip())


def _ts_to_secs(ts: str) -> float:
    """'MM:SS.mmm' or 'HH:MM:SS.mmm' → float seconds."""
    parts = ts.split(":")
    if len(parts) == 3:
        h, m, s = parts
        return float(h) * 3600 + float(m) * 60 + float(s)
    m, s = parts
    return float(m) * 60 + float(s)


def _secs_to_ts(secs: float) -> str:
    """float seconds → 'MM:SS.mmm'."""
    m = int(secs // 60)
    return f"{m:02d}:{secs - m * 60:06.3f}"


def _find_in_whisper(whisper_text: str, search: str) -> float | None:
    """Return the start-time (seconds) of the first whisper segment whose
    text overlaps significantly with *search*. Returns None if not found."""
    needles = set(search.lower().split())
    if not needles:
        return None
    for line in whisper_text.splitlines():
        m = re.match(r"\[(\d+\.\d+) --> \d+\.\d+\]\s+(.*)", line)
        if not m:
            continue
        seg_words = set(m.group(2).lower().split())
        if len(needles & seg_words) >= max(1, len(needles) // 3):
            return float(m.group(1))
    return None


def _db_to_linear(db: float) -> float:
    return 10 ** (db / 20)


def _generate_synthetic_music(cue_type: str, duration: float, output_path: Path) -> None:
    """Write a synthetic audio placeholder using ffmpeg built-ins."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    dur = max(0.5, duration)
    if cue_type in ("intro", "outro"):
        fade_out_st = max(0, dur - 2)
        af = f"afade=t=in:st=0:d=1,afade=t=out:st={fade_out_st}:d=2,volume=0.4"
        freq = 330
    elif cue_type == "bed":
        af = "volume=0.03"
        freq = 220
    elif cue_type == "sting":
        af = f"afade=t=out:st={max(0, dur - 0.3)}:d=0.3,volume=0.6"
        freq = 880
    else:  # sfx
        af = f"afade=t=out:st={max(0, dur - 0.2)}:d=0.2,volume=0.5"
        freq = 660
    cmd = (
        f'ffmpeg -y -f lavfi -i "sine=frequency={freq}:duration={dur}" '
        f'-af "{af}" -ac 1 -ar 44100 "{output_path}"'
    )
    subprocess.run(cmd, shell=True, capture_output=True, cwd=str(WORKSPACE))


# ── Shared pipeline state ─────────────────────────────────────────────────────

@dataclass
class _PipelineState:
    episode_dir: Path = None
    model: str = ""
    transcript: dict = field(default_factory=dict)

    # Phase 1 — voice generation
    script_path: Path = None
    overlap_manifest: list = field(default_factory=list)

    # Phase 1b — music plan (arrives in parallel with voice gen)
    music_plan: dict = field(default_factory=dict)
    music_plan_path: Path = None
    music_plan_ready: bool = False

    # Phase 2 — generated audio
    audio_path: Path = None

    # Phase 3 — whisper
    whisper_output: str = ""
    whisper_ready: bool = False

    # ── Output directory layout ───────────────────────────────────────────────
    # audio-artifacts/
    #   scripts/   — SSML/VibeVoice script, overlap manifest, music plan
    #   speech/    — raw TTS audio
    #   whisper/   — Whisper transcription
    #   mix/       — timestamped transcript, mix plan, clips, final preview

    @property
    def artifacts_dir(self) -> Path:
        return self.episode_dir / "audio-artifacts"

    @property
    def scripts_dir(self) -> Path:
        return self.artifacts_dir / "scripts"

    @property
    def speech_dir(self) -> Path:
        return self.artifacts_dir / "speech"

    @property
    def whisper_dir(self) -> Path:
        return self.artifacts_dir / "whisper"

    @property
    def mix_dir(self) -> Path:
        return self.artifacts_dir / "mix"


_state = _PipelineState()


# ── Resume helpers ────────────────────────────────────────────────────────────

def _detect_model_from_artifacts(ep_dir: Path) -> str | None:
    """Infer which TTS model was used by checking which script subdirectory exists."""
    scripts_dir = ep_dir / "audio-artifacts" / "scripts"
    if (scripts_dir / "mai2" / "script.xml").exists():
        return "mai-2"
    if (scripts_dir / "vibevoice" / "script.txt").exists():
        return "vibe-voice"
    return None


def _load_state_for_resume(ep_dir: Path, model: str) -> None:
    """Populate _state from every artifact file that already exists on disk."""
    _state.episode_dir = ep_dir
    _state.model = model

    transcript_path = ep_dir / "transcript.json"
    if transcript_path.exists():
        _state.transcript = json.loads(transcript_path.read_text())

    script_path = (
        _state.scripts_dir / "mai2" / "script.xml"
        if model == "mai-2"
        else _state.scripts_dir / "vibevoice" / "script.txt"
    )
    if script_path.exists():
        _state.script_path = script_path

    manifest_path = _state.scripts_dir / "overlap-manifest.json"
    if manifest_path.exists():
        _state.overlap_manifest = json.loads(manifest_path.read_text())

    music_plan_path = _state.scripts_dir / "music-plan.json"
    if music_plan_path.exists():
        _state.music_plan = json.loads(music_plan_path.read_text())
        _state.music_plan_path = music_plan_path
        _state.music_plan_ready = True

    audio_path = _state.speech_dir / "speech.mp3"
    if audio_path.exists():
        _state.audio_path = audio_path

    whisper_txt = _state.whisper_dir / "whisper-transcript.txt"
    if whisper_txt.exists():
        _state.whisper_output = whisper_txt.read_text()
        _state.whisper_ready = True


def _make_fake_agent_response(text: str) -> AgentExecutorResponse:
    """Wrap plain text in an AgentExecutorResponse so executor @handlers that
    expect one can be targeted directly during resume."""
    msg = Message("assistant", [text])
    return AgentExecutorResponse(
        executor_id="resume",
        agent_response=AgentResponse(messages=[msg]),
        full_conversation=[msg],
    )


# ── Typed messages ────────────────────────────────────────────────────────────

@dataclass
class TranscriptLoaded:
    transcript_json: str
    episode_dir: Path
    model: str


@dataclass
class MusicPlanReady:
    plan: dict
    plan_path: Path


@dataclass
class WhisperReady:
    transcription: str
    audio_path: Path


@dataclass
class ModelSelectRequest:
    transcript_preview: str
    prompt: str = (
        "Which model would you like to use for audio generation?\n"
        "  • mai-2       — MAI Voice 2 API (cloud, requires API key)\n"
        "  • vibe-voice  — VibeVoice 7B (local GPU, requires placement step)\n\n"
        "Enter model name:"
    )


@dataclass
class VibeVoiceReadyRequest:
    instructions: str
    script_path: str
    prompt: str = "When your audio file is in place, type 'ready' to continue:"


# ── Executors ─────────────────────────────────────────────────────────────────

class TranscriptLoaderExecutor(Executor):
    """Entry point. Loads transcript.json, then fans out to voice generator
    AND music director in parallel."""

    def __init__(self, id: str, voice_gen_id: str, music_director_id: str,
                 slug: str | None, model: str | None, resume: bool = False):
        super().__init__(id=id)
        self._voice_gen_id = voice_gen_id
        self._music_director_id = music_director_id
        self._slug = slug
        self._cli_model = model
        self._resume = resume

    @handler
    async def start(self, request: AgentExecutorRequest, ctx: WorkflowContext) -> None:
        ep_dir = _find_episode_dir(self._slug)

        if self._resume:
            await self._do_resume(ep_dir, ctx)
            return

        _state.episode_dir = ep_dir

        transcript_path = ep_dir / "transcript.json"
        if not transcript_path.exists():
            await ctx.yield_output(
                f"No transcript.json found at {transcript_path}.\n"
                "Run the Episode Production Workflow (Section 3) first."
            )
            return

        transcript_json = transcript_path.read_text()
        _state.transcript = json.loads(transcript_json)

        if self._cli_model and self._cli_model in VALID_MODELS:
            _state.model = self._cli_model
            await self._fan_out(transcript_json, ctx)
        else:
            preview = transcript_json[:600] + "…"
            await ctx.request_info(
                request_data=ModelSelectRequest(transcript_preview=preview),
                response_type=str,
            )

    @response_handler
    async def handle_model_select(
        self,
        original_request: ModelSelectRequest,
        response: str,
        ctx: WorkflowContext,
    ) -> None:
        model = response.strip().lower()
        if model not in VALID_MODELS:
            await ctx.yield_output(
                f"Unknown model '{model}'. Choose: {', '.join(sorted(VALID_MODELS))}"
            )
            await ctx.request_info(request_data=original_request, response_type=str)
            return

        _state.model = model
        transcript_json = json.dumps(_state.transcript)
        await self._fan_out(transcript_json, ctx)

    async def _fan_out(self, transcript_json: str, ctx: WorkflowContext) -> None:
        await ctx.yield_output(
            f"Episode: {_state.episode_dir.name}\n"
            f"Model:   {_state.model}\n"
            f"Utterances: {len(_state.transcript.get('utterances', []))}\n\n"
            "Starting voice generator and music director in parallel…"
        )

        prompt = (
            f"Transcript JSON:\n\n{transcript_json}\n\n"
            "Convert this transcript to the appropriate script format. "
            "Include the overlap manifest."
        )

        # Send directly to the model-specific voice generator — skipping the
        # VoiceGenFanOut middleman hop so ssml_gen/vv_gen starts in the same
        # superstep as music_director rather than one superstep later.
        voice_target = "ssml_gen" if _state.model == "mai-2" else "vv_gen"
        await ctx.send_message(
            AgentExecutorRequest(
                messages=[Message(role="user", contents=[prompt])],
                should_respond=True,
            ),
            target_id=voice_target,
        )

        await ctx.send_message(
            AgentExecutorRequest(
                messages=[Message(
                    role="user",
                    contents=[
                        f"Design the music and SFX plan for this episode.\n\n"
                        f"Transcript JSON:\n\n{transcript_json}"
                    ],
                )],
                should_respond=True,
            ),
            target_id=self._music_director_id,
        )

    async def _do_resume(self, ep_dir: Path, ctx: WorkflowContext) -> None:
        detected_model = self._cli_model or _detect_model_from_artifacts(ep_dir)
        if not detected_model:
            await ctx.yield_output(
                "Resume: no existing script artifacts found.\n"
                "Run without --resume to start fresh."
            )
            return

        _load_state_for_resume(ep_dir, detected_model)

        mix_plan_path   = _state.mix_dir    / "mix-plan.json"
        ts_path         = _state.mix_dir    / "timestamped-transcript.json"
        whisper_path    = _state.whisper_dir / "whisper-transcript.txt"
        audio_path      = _state.speech_dir  / "speech.mp3"
        music_plan_path = _state.scripts_dir / "music-plan.json"

        header = f"Resuming: {ep_dir.name} | Model: {detected_model}\n"

        # ── Checkpoint: re-run ffmpeg from saved mix plan ─────────────────────
        if mix_plan_path.exists():
            await ctx.yield_output(
                header + "Checkpoint 5/5 — mix plan exists: re-running ffmpeg execution"
            )
            await ctx.send_message(
                _make_fake_agent_response(mix_plan_path.read_text()),
                target_id="mix_plan",
            )
            return

        # ── Checkpoint: re-run audio mixer LLM from timestamped transcript ────
        if ts_path.exists():
            await ctx.yield_output(
                header + "Checkpoint 4/5 — timestamped transcript exists: re-running audio mixer"
            )
            original_json = json.dumps(_state.transcript, indent=2)
            overlap_json  = json.dumps(_state.overlap_manifest, indent=2)
            audio_rel     = (
                str(_state.audio_path.relative_to(WORKSPACE))
                if _state.audio_path else "(not found)"
            )
            ep_rel      = str(ep_dir.relative_to(WORKSPACE))
            music_dir   = _state.mix_dir / "music"
            music_files = (
                sorted(str(p.relative_to(WORKSPACE)) for p in music_dir.glob("*"))
                if music_dir.exists() else []
            )
            await ctx.send_message(
                AgentExecutorRequest(
                    messages=[Message(role="user", contents=[
                        f"Timestamped transcript JSON:\n```json\n{ts_path.read_text()}\n```\n\n"
                        f"Original transcript JSON:\n```json\n{original_json}\n```\n\n"
                        f"Overlap manifest:\n```json\n{overlap_json}\n```\n\n"
                        f"Generated audio file: {audio_rel}\n"
                        f"Episode directory:    {ep_rel}\n"
                        f"Music/SFX files available: "
                        f"{music_files or ['(none yet — include commands but note missing files)']}\n\n"
                        "Produce the ffmpeg mix plan JSON."
                    ])],
                    should_respond=True,
                ),
                target_id="audio_mixer",
            )
            return

        # ── Checkpoint: re-run from speech audio (whisper + optional music) ───
        if audio_path.exists():
            music_missing = not music_plan_path.exists()
            await ctx.yield_output(
                header + "Checkpoint 3/5 — speech audio exists: re-running"
                + (" whisper + music director" if music_missing else " whisper")
            )

            if whisper_path.exists():
                await ctx.yield_output("  Whisper transcript already on disk — skipping whisper run")
                await ctx.send_message(
                    WhisperReady(
                        transcription=_state.whisper_output,
                        audio_path=audio_path,
                    ),
                    target_id="audio_tech_fan_in",
                )
            else:
                await ctx.send_message(
                    WhisperReady(transcription="", audio_path=audio_path),
                    target_id="whisper",
                )

            if music_missing:
                await ctx.send_message(
                    AgentExecutorRequest(
                        messages=[Message(role="user", contents=[
                            f"Design the music and SFX plan for this episode.\n\n"
                            f"Transcript JSON:\n\n{json.dumps(_state.transcript)}"
                        ])],
                        should_respond=True,
                    ),
                    target_id="music_director",
                )
            else:
                await ctx.send_message(
                    MusicPlanReady(plan=_state.music_plan, plan_path=music_plan_path),
                    target_id="audio_tech_fan_in",
                )
            return

        # ── Checkpoint: re-run audio generation from script ───────────────────
        if _state.script_path and _state.script_path.exists():
            music_missing    = not music_plan_path.exists()
            audio_gen_target = "mai2_audio" if detected_model == "mai-2" else "vv_hitl"
            script_content   = _state.script_path.read_text()
            await ctx.yield_output(
                header + "Checkpoint 2/5 — script exists: re-running audio generation"
                + (" + music director" if music_missing else "")
            )
            await ctx.send_message(
                AgentExecutorRequest(
                    messages=[Message(role="user", contents=[
                        f"Model: {detected_model}\n"
                        f"Script path: {_state.script_path.relative_to(WORKSPACE)}\n"
                        f"Script content:\n\n{script_content}\n\n"
                        "Generate audio from this script."
                    ])],
                    should_respond=True,
                ),
                target_id=audio_gen_target,
            )
            if music_missing:
                await ctx.send_message(
                    AgentExecutorRequest(
                        messages=[Message(role="user", contents=[
                            f"Design the music and SFX plan for this episode.\n\n"
                            f"Transcript JSON:\n\n{json.dumps(_state.transcript)}"
                        ])],
                        should_respond=True,
                    ),
                    target_id="music_director",
                )
            else:
                await ctx.send_message(
                    MusicPlanReady(plan=_state.music_plan, plan_path=music_plan_path),
                    target_id="audio_tech_fan_in",
                )
            return

        # ── No intermediate artifacts: run full workflow with detected model ───
        await ctx.yield_output(
            header + "Checkpoint 1/5 — no intermediate artifacts: starting full workflow"
        )
        await self._fan_out(json.dumps(_state.transcript), ctx)


class ScriptSaveExecutor(Executor):
    """Saves the voice generator output (script file + overlap manifest).
    Then routes to AudioGenDispatch."""

    def __init__(self, id: str, audio_gen_id: str, model: str):
        super().__init__(id=id)
        self._audio_gen_id = audio_gen_id
        self._model = model

    @handler
    async def save(self, response: AgentExecutorResponse, ctx: WorkflowContext) -> None:
        text = response.agent_response.text
        ep_dir = _state.episode_dir

        if _state.model == "mai-2":
            script_content = _extract_section(text, "===SCRIPT===", "===END_SCRIPT===")
            script_dir     = _state.scripts_dir / "mai2"
            script_path    = script_dir / "script.xml"
        else:
            script_content = _extract_section(text, "===SCRIPT===", "===END_SCRIPT===")
            script_dir     = _state.scripts_dir / "vibevoice"
            script_path    = script_dir / "script.txt"

        overlap_raw = _extract_section(
            text, "===OVERLAP_MANIFEST===", "===END_OVERLAP_MANIFEST==="
        )

        script_dir.mkdir(parents=True, exist_ok=True)
        script_path.write_text(script_content.strip())
        _state.script_path = script_path

        try:
            _state.overlap_manifest = json.loads(overlap_raw.strip() or "[]")
        except json.JSONDecodeError:
            _state.overlap_manifest = []

        manifest_path = _state.scripts_dir / "overlap-manifest.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(_state.overlap_manifest, indent=2))

        await ctx.yield_output(
            f"Script saved:          {script_path.relative_to(WORKSPACE)}\n"
            f"Overlap manifest:      {manifest_path.relative_to(WORKSPACE)}\n"
            f"Overlapping utterances: {len(_state.overlap_manifest)}"
        )

        await ctx.send_message(
            AgentExecutorRequest(
                messages=[Message(role="user", contents=[
                    f"Model: {_state.model}\n"
                    f"Script path: {script_path.relative_to(WORKSPACE)}\n"
                    f"Script content:\n\n{script_content}\n\n"
                    "Generate audio from this script."
                ])],
                should_respond=True,
            ),
            target_id=self._audio_gen_id,
        )


class MusicPlanSaveExecutor(Executor):
    """Saves the music plan JSON and signals AudioTechFanIn."""

    def __init__(self, id: str, audio_tech_fan_in_id: str):
        super().__init__(id=id)
        self._fan_in_id = audio_tech_fan_in_id

    @handler
    async def save(self, response: AgentExecutorResponse, ctx: WorkflowContext) -> None:
        text = response.agent_response.text.strip()

        # Strip markdown fences if present
        text = re.sub(r"^```[a-z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text.rstrip())

        try:
            plan = json.loads(text)
        except json.JSONDecodeError:
            await ctx.yield_output(f"Music plan JSON parse error — raw output:\n{text}")
            return

        _state.music_plan = plan
        plan_path = _state.scripts_dir / "music-plan.json"
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        plan_path.write_text(json.dumps(plan, indent=2))
        _state.music_plan_path = plan_path
        _state.music_plan_ready = True

        await ctx.yield_output(
            f"Music plan saved: {plan_path.relative_to(WORKSPACE)}\n"
            f"Cues planned: {len(plan.get('cues', []))}"
        )

        await ctx.send_message(
            MusicPlanReady(plan=plan, plan_path=plan_path),
            target_id=self._fan_in_id,
        )


class MAI2AudioExecutor(Executor):
    """Calls the MAI Voice 2 API with the SSML script, saves the audio."""

    def __init__(self, id: str, whisper_id: str):
        super().__init__(id=id)
        self._whisper_id = whisper_id

    @handler
    async def generate(self, request: AgentExecutorRequest, ctx: WorkflowContext) -> None:
        script_path = _state.script_path
        ep_dir      = _state.episode_dir

        await ctx.yield_output(
            f"Submitting SSML to MAI Voice 2 API…\n"
            f"Script: {script_path.relative_to(WORKSPACE)}"
        )

        audio_dir = _state.speech_dir
        audio_dir.mkdir(parents=True, exist_ok=True)
        audio_path = audio_dir / "speech.mp3"

        ssml_content = script_path.read_text()

        try:
            # Import the synthesize function from the existing mai-2 helper
            import importlib.util
            spec = importlib.util.spec_from_file_location("mai2", MAI2_SCRIPT)
            mai2 = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mai2)

            # Override the output directory
            mai2.OUT_DIR = audio_dir
            result_path = mai2.synthesize_to_file(ssml_content, "speech.mp3")
            _state.audio_path = result_path

            await ctx.yield_output(
                f"Audio generated: {result_path.relative_to(WORKSPACE)}"
            )
        except Exception as exc:
            await ctx.yield_output(
                f"MAI-2 API call failed: {exc}\n\n"
                f"Place your audio file manually at:\n"
                f"  {audio_path.relative_to(WORKSPACE)}\n"
                "Then restart the workflow."
            )
            return

        _state.audio_path = audio_path
        await ctx.send_message(
            WhisperReady(transcription="", audio_path=audio_path),
            target_id=self._whisper_id,
        )


class VibeVoiceHITLExecutor(Executor):
    """Instructs the user to generate audio locally with VibeVoice 7B,
    waits for them to place the output file, then routes to WhisperExecutor."""

    def __init__(self, id: str, whisper_id: str):
        super().__init__(id=id)
        self._whisper_id = whisper_id

    @handler
    async def instruct(self, request: AgentExecutorRequest, ctx: WorkflowContext) -> None:
        ep_dir = _state.episode_dir
        script_path = _state.script_path
        audio_path  = _state.speech_dir / "speech.mp3"
        audio_path.parent.mkdir(parents=True, exist_ok=True)

        instructions = (
            f"VibeVoice 7B — Manual Audio Generation\n"
            f"{'─' * 45}\n\n"
            f"1. Open the VibeVoice notebook:\n"
            f"   content/4-Executing-the-workflow/vibevoice.ipynb\n\n"
            f"2. Upload the script file:\n"
            f"   {script_path.relative_to(WORKSPACE)}\n\n"
            f"3. Set speaker voices in the notebook:\n"
        )
        for host in _state.transcript.get("hosts", []):
            vv_voice = next(
                (v.replace("vibevoice: ", "").strip()
                 for v in host.get("voices", []) if "vibevoice:" in v),
                "en-Alice_woman.wav",
            )
            instructions += f"   {host['name']}: {vv_voice}\n"

        instructions += (
            f"\n4. Run all cells. The notebook will produce a single audio file.\n\n"
            f"5. Download the audio and place it at:\n"
            f"   {audio_path.relative_to(WORKSPACE)}\n\n"
            f"6. Come back here and type 'ready' to continue."
        )

        await ctx.request_info(
            request_data=VibeVoiceReadyRequest(
                instructions=instructions,
                script_path=str(script_path.relative_to(WORKSPACE)),
            ),
            response_type=str,
        )

    @response_handler
    async def handle_ready(
        self,
        original_request: VibeVoiceReadyRequest,
        response: str,
        ctx: WorkflowContext,
    ) -> None:
        if response.strip().lower() != "ready":
            await ctx.yield_output("Waiting… type 'ready' when the audio file is in place.")
            await ctx.request_info(request_data=original_request, response_type=str)
            return

        audio_path = _state.speech_dir / "speech.mp3"
        if not audio_path.exists():
            await ctx.yield_output(
                f"No audio file found at {audio_path.relative_to(WORKSPACE)}.\n"
                "Place the file there and type 'ready' again."
            )
            await ctx.request_info(request_data=original_request, response_type=str)
            return

        _state.audio_path = audio_path
        await ctx.yield_output(
            f"Audio file confirmed: {audio_path.relative_to(WORKSPACE)}"
        )
        await ctx.send_message(
            WhisperReady(transcription="", audio_path=audio_path),
            target_id=self._whisper_id,
        )


class WhisperExecutor(Executor):
    """Runs the whisper-cli tool on the generated audio to get timestamps,
    then signals AudioTechFanIn."""

    def __init__(self, id: str, fan_in_id: str):
        super().__init__(id=id)
        self._fan_in_id = fan_in_id

    @handler
    async def transcribe(self, msg: WhisperReady, ctx: WorkflowContext) -> None:
        audio_path = _state.audio_path
        await ctx.yield_output(
            f"Running Whisper transcription on: {audio_path.relative_to(WORKSPACE)}"
        )

        output_dir = _state.whisper_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        whisper_txt = output_dir / "whisper-transcript.txt"

        try:
            result = subprocess.run(
                ["whisper-cli", str(audio_path), "--output-format", "txt",
                 "--output-dir", str(output_dir)],
                capture_output=True, text=True, check=True, timeout=300,
            )
            transcription = result.stdout or whisper_txt.read_text()
        except FileNotFoundError:
            # whisper-cli not available — try faster-whisper (no torch required)
            try:
                from faster_whisper import WhisperModel
                await ctx.yield_output(
                    "whisper-cli not found. Falling back to faster-whisper…"
                )
                fw_model = WhisperModel("tiny.en", device="cpu", compute_type="int8")
                segments, _ = fw_model.transcribe(str(audio_path))
                lines = [
                    f"[{seg.start:.2f} --> {seg.end:.2f}]  {seg.text.strip()}"
                    for seg in segments
                ]
                transcription = "\n".join(lines) if lines else "(no segments)"
            except ImportError:
                # fall back to openai-whisper if installed
                try:
                    import whisper as _whisper
                    await ctx.yield_output(
                        "faster-whisper not found. Falling back to openai-whisper…"
                    )
                    ow_model = _whisper.load_model("base")
                    wresult = ow_model.transcribe(str(audio_path))
                    lines = [
                        f"[{seg['start']:.2f} --> {seg['end']:.2f}]  {seg['text'].strip()}"
                        for seg in wresult.get("segments", [])
                    ]
                    transcription = "\n".join(lines) if lines else wresult.get("text", "")
                except ImportError:
                    await ctx.yield_output(
                        "No whisper backend found. Install faster-whisper:\n"
                        "  pip install faster-whisper\n\n"
                        "Continuing with empty transcription — timestamps will be estimated."
                    )
                    transcription = "(whisper not available — no timestamps)"
        except subprocess.CalledProcessError as exc:
            await ctx.yield_output(
                f"Whisper failed (exit {exc.returncode}):\n{exc.stderr}\n\n"
                "Continuing with empty transcription."
            )
            transcription = f"(whisper error: {exc.stderr[:200]})"
        except subprocess.TimeoutExpired:
            await ctx.yield_output("Whisper timed out after 5 minutes.")
            transcription = "(whisper timed out)"

        whisper_txt.write_text(transcription)
        _state.whisper_output = transcription
        _state.whisper_ready = True

        await ctx.yield_output(
            f"Whisper transcript saved: {whisper_txt.relative_to(WORKSPACE)}"
        )

        await ctx.send_message(
            WhisperReady(transcription=transcription, audio_path=audio_path),
            target_id=self._fan_in_id,
        )


class AudioTechFanIn(Executor):
    """Waits for BOTH the Whisper transcription AND the music plan before
    forwarding to the Audio Technician agent."""

    def __init__(self, id: str, audio_tech_id: str):
        super().__init__(id=id)
        self._audio_tech_id = audio_tech_id
        self._whisper: WhisperReady | None = None
        self._music: MusicPlanReady | None = None

    @handler
    async def recv_whisper(self, msg: WhisperReady, ctx: WorkflowContext) -> None:
        self._whisper = msg
        if self._music is not None:
            await self._dispatch(ctx)
        else:
            await ctx.yield_output(
                "Whisper transcription received. Waiting for music plan…"
            )

    @handler
    async def recv_music(self, msg: MusicPlanReady, ctx: WorkflowContext) -> None:
        self._music = msg
        if self._whisper is not None:
            await self._dispatch(ctx)
        else:
            await ctx.yield_output(
                "Music plan received. Waiting for Whisper transcription…"
            )

    async def _dispatch(self, ctx: WorkflowContext) -> None:
        await ctx.yield_output(
            "Both Whisper transcription and music plan ready. "
            "Calling Audio Technician…"
        )

        transcript_json = json.dumps(_state.transcript, indent=2)
        music_plan_json = json.dumps(self._music.plan, indent=2)
        overlap_json    = json.dumps(_state.overlap_manifest, indent=2)

        await ctx.send_message(
            AgentExecutorRequest(
                messages=[Message(role="user", contents=[
                    f"Original transcript JSON:\n```json\n{transcript_json}\n```\n\n"
                    f"Whisper CLI transcription:\n```\n{self._whisper.transcription}\n```\n\n"
                    f"Music plan JSON:\n```json\n{music_plan_json}\n```\n\n"
                    f"Overlap manifest JSON:\n```json\n{overlap_json}\n```\n\n"
                    f"Audio file: {_state.audio_path.relative_to(WORKSPACE)}\n\n"
                    "Produce the timestamped transcript JSON."
                ])],
                should_respond=True,
            ),
            target_id=self._audio_tech_id,
        )


class TimestampedTranscriptSaveExecutor(Executor):
    """Saves the Audio Technician's timestamped transcript, then routes to
    the Audio Mixer."""

    def __init__(self, id: str, audio_mixer_id: str):
        super().__init__(id=id)
        self._audio_mixer_id = audio_mixer_id

    @handler
    async def save(self, response: AgentExecutorResponse, ctx: WorkflowContext) -> None:
        text = response.agent_response.text.strip()
        text = re.sub(r"^```[a-z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text.rstrip())

        try:
            ts_transcript = json.loads(text)
        except json.JSONDecodeError as exc:
            await ctx.yield_output(
                f"Timestamped transcript JSON parse error: {exc}\n\nRaw:\n{text[:500]}"
            )
            return

        # ── Timestamp validation ──────────────────────────────────────────────
        # Guard against the Audio Technician assigning timestamps beyond the
        # actual audio file duration (a common hallucination for later utterances).
        if _state.audio_path and _state.audio_path.exists():
            audio_dur = _get_audio_duration(_state.audio_path)
            utterances = ts_transcript.get("utterances", [])
            fixed: list[str] = []
            prev_end = 0.0

            for utt in utterances:
                ts = utt.setdefault("timestamps", {})
                start = _ts_to_secs(ts.get("start", "00:00.000"))
                end   = _ts_to_secs(ts.get("end",   "00:00.000"))

                if start >= audio_dur:
                    # Utterance entirely outside audio — try whisper text search
                    found = _find_in_whisper(
                        _state.whisper_output, utt.get("text", "")[:80]
                    )
                    if found is not None:
                        start = found
                        end   = min(found + max(1.0, end - start), audio_dur)
                    else:
                        # Fallback: divide remaining audio equally among out-of-bounds utterances
                        remaining = sum(
                            1 for u in utterances
                            if _ts_to_secs(
                                u.get("timestamps", {}).get("start", "00:00.000")
                            ) >= audio_dur
                        )
                        slice_dur = (audio_dur - prev_end) / max(remaining, 1)
                        start = prev_end
                        end   = min(prev_end + slice_dur, audio_dur)
                    ts["start"]      = _secs_to_ts(start)
                    ts["end"]        = _secs_to_ts(end)
                    ts["confidence"] = "estimated"
                    fixed.append(utt["id"])
                elif end > audio_dur:
                    ts["end"]        = _secs_to_ts(audio_dur)
                    ts["confidence"] = "clamped"
                    fixed.append(utt["id"])

                prev_end = _ts_to_secs(ts["end"])

            ts_transcript["total_duration"] = _secs_to_ts(audio_dur)

            if fixed:
                await ctx.yield_output(
                    f"Timestamp fix ({len(fixed)} utterances clamped/re-estimated "
                    f"— audio is {_secs_to_ts(audio_dur)}): {', '.join(fixed)}"
                )
        # ─────────────────────────────────────────────────────────────────────

        out_path = _state.mix_dir / "timestamped-transcript.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(ts_transcript, indent=2))

        await ctx.yield_output(
            f"Timestamped transcript saved: {out_path.relative_to(WORKSPACE)}"
        )

        transcript_json  = json.dumps(ts_transcript, indent=2)
        original_json    = json.dumps(_state.transcript, indent=2)
        overlap_json     = json.dumps(_state.overlap_manifest, indent=2)
        audio_rel        = str(_state.audio_path.relative_to(WORKSPACE))
        ep_rel           = str(_state.episode_dir.relative_to(WORKSPACE))

        # List any music files already present in the mix directory
        music_dir   = _state.mix_dir / "music"
        music_files = sorted(str(p.relative_to(WORKSPACE)) for p in music_dir.glob("*")) \
            if music_dir.exists() else []

        await ctx.send_message(
            AgentExecutorRequest(
                messages=[Message(role="user", contents=[
                    f"Timestamped transcript JSON:\n```json\n{transcript_json}\n```\n\n"
                    f"Original transcript JSON:\n```json\n{original_json}\n```\n\n"
                    f"Overlap manifest:\n```json\n{overlap_json}\n```\n\n"
                    f"Generated audio file: {audio_rel}\n"
                    f"Episode directory:    {ep_rel}\n"
                    f"Music/SFX files available: {music_files or ['(none yet — include commands but note missing files)']}\n\n"
                    "Produce the ffmpeg mix plan JSON."
                ])],
                should_respond=True,
            ),
            target_id=self._audio_mixer_id,
        )


class MixPlanExecutor(Executor):
    """Receives the Audio Mixer's ffmpeg plan, saves it, then executes each
    step's commands to produce the final preview audio.

    Steps 3, 4, and 5 are overridden with deterministic Python implementations:
      Step 3 — overlap-aware concat (no silence gap at overlap transitions)
      Step 4 — synthetic music generation + real adelay/amix overlay commands
      Step 5 — normalise the right input (with-music or speech-only)
    """

    @handler
    async def process(self, response: AgentExecutorResponse, ctx: WorkflowContext) -> None:
        text = response.agent_response.text.strip()
        text = re.sub(r"^```[a-z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text.rstrip())

        try:
            plan = json.loads(text)
        except json.JSONDecodeError as exc:
            await ctx.yield_output(
                f"Mix plan JSON parse error: {exc}\n\nRaw:\n{text[:500]}"
            )
            return

        plan_path = _state.mix_dir / "mix-plan.json"
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        plan_path.write_text(json.dumps(plan, indent=2))
        await ctx.yield_output(
            f"Mix plan saved: {plan_path.relative_to(WORKSPACE)}\n"
            f"Steps: {len(plan.get('steps', []))}"
        )

        clips_dir = _state.mix_dir / "clips"
        clips_dir.mkdir(parents=True, exist_ok=True)

        # ── Pre-generate synthetic music files ────────────────────────────────
        tf_cues   = plan.get("transcript_with_files", {}).get("music_cues", [])
        orig_cues = {c["id"]: c for c in _state.music_plan.get("cues", [])}

        await ctx.yield_output("Checking music/SFX files…")
        for tf_cue in tf_cues:
            cue_path = WORKSPACE / tf_cue["file"]
            if cue_path.exists():
                continue
            orig     = orig_cues.get(tf_cue["id"], {})
            cue_type = orig.get("type", "sfx")
            ts       = tf_cue.get("timestamps", {})
            dur = max(
                0.5,
                _ts_to_secs(ts.get("end",   "00:01.000"))
                - _ts_to_secs(ts.get("start", "00:00.000")),
            )
            _generate_synthetic_music(cue_type, dur, cue_path)
            await ctx.yield_output(
                f"  ✓ Synthetic {cue_type}: {cue_path.name}"
            )
        # ─────────────────────────────────────────────────────────────────────

        # Overlap pairs: {(overlaps_with_id, utterance_id)}
        overlap_pairs = {
            (o["overlaps_with"], o["utterance_id"])
            for o in _state.overlap_manifest
        }

        # Track which file feeds into step 5
        episode_speech_path = _state.mix_dir / "episode_speech.mp3"
        mix_input           = episode_speech_path   # updated after step 4

        errors: list[str] = []

        for step in plan.get("steps", []):
            step_num  = step.get("step", "?")
            step_desc = step.get("description", "")
            commands  = step.get("commands", [])

            await ctx.yield_output(f"Step {step_num}: {step_desc}")

            # ── Step 3 override: overlap-aware concat ─────────────────────────
            if step_num == 3 and "concatenate" in step_desc.lower():
                # Collect valid (non-empty) base utterance clips, sorted
                utt_clips = sorted(
                    p for p in clips_dir.glob("u[0-9]*.mp3")
                    if "_overlaid_" not in p.stem and p.stat().st_size > 1000
                )
                utt_ids = [p.stem for p in utt_clips]

                if not utt_ids:
                    await ctx.yield_output("  [WARN] No valid utterance clips found — skipping concat")
                    continue

                # Ensure silence clip exists
                silence_path = clips_dir / "silence_200ms.mp3"
                if not silence_path.exists():
                    subprocess.run(
                        'ffmpeg -y -f lavfi -i anullsrc=r=44100:cl=mono -t 0.2 '
                        f'"{silence_path}"',
                        shell=True, capture_output=True, cwd=str(WORKSPACE),
                    )

                # Build input list: omit silence gap at overlap transitions
                inputs: list[Path] = []
                for i, uid in enumerate(utt_ids):
                    inputs.append(clips_dir / f"{uid}.mp3")
                    if i < len(utt_ids) - 1:
                        next_uid = utt_ids[i + 1]
                        if (uid, next_uid) not in overlap_pairs:
                            inputs.append(silence_path)

                n          = len(inputs)
                input_args = " ".join(f'-i "{p}"' for p in inputs)
                filt       = "".join(f"[{j}:a]" for j in range(n)) + f"concat=n={n}:v=0:a=1"
                out_cmd    = (
                    f'ffmpeg -y {input_args} '
                    f'-filter_complex "{filt}" -ac 1 "{episode_speech_path}"'
                )
                result = subprocess.run(
                    out_cmd, shell=True, capture_output=True,
                    text=True, cwd=str(WORKSPACE), timeout=300,
                )
                if result.returncode == 0:
                    await ctx.yield_output(
                        f"  ✓ Overlap-aware concat: {len(utt_ids)} clips "
                        f"({sum(1 for i, u in enumerate(utt_ids[:-1]) if (u, utt_ids[i+1]) in overlap_pairs)} "
                        f"seamless overlaps)"
                    )
                else:
                    errors.append(f"Step 3 concat: {result.stderr[:200]}")
                    await ctx.yield_output(f"  [WARN] Concat failed:\n  {result.stderr[:200]}")
                continue
            # ─────────────────────────────────────────────────────────────────

            # ── Step 4 override: music overlay ────────────────────────────────
            if step_num == 4 and "music" in step_desc.lower():
                if not episode_speech_path.exists():
                    await ctx.yield_output(
                        "  [WARN] episode_speech.mp3 missing — skipping music overlay"
                    )
                    continue

                current = episode_speech_path
                for tf_cue in sorted(
                    tf_cues,
                    key=lambda c: _ts_to_secs(c["timestamps"]["start"]),
                ):
                    cue_file = WORKSPACE / tf_cue["file"]
                    if not cue_file.exists():
                        await ctx.yield_output(
                            f"  [WARN] Music file missing: {tf_cue['file']} — skipping cue"
                        )
                        continue

                    orig     = orig_cues.get(tf_cue["id"], {})
                    vol      = _db_to_linear(orig.get("volume_db", -18))
                    cue_ts   = tf_cue.get("timestamps", {})
                    start_s  = _ts_to_secs(cue_ts.get("start", "00:00.000"))
                    end_s    = _ts_to_secs(cue_ts.get("end",   "00:01.000"))
                    cue_dur  = max(0.1, end_s - start_s)
                    delay_ms = int(start_s * 1000)
                    nxt      = _state.mix_dir / f"episode_mix_{tf_cue['id']}.mp3"

                    overlay_cmd = (
                        f'ffmpeg -y -i "{current}" -i "{cue_file}" '
                        f'-filter_complex '
                        f'"[1:a]atrim=duration={cue_dur}[c];'
                        f'[c]adelay={delay_ms}|{delay_ms}[cd];'
                        f'[0:a][cd]amix=inputs=2:duration=first:weights=1 {vol:.4f}" '
                        f'-ac 1 "{nxt}"'
                    )
                    res = subprocess.run(
                        overlay_cmd, shell=True, capture_output=True,
                        text=True, cwd=str(WORKSPACE), timeout=120,
                    )
                    if res.returncode == 0:
                        current = nxt
                        await ctx.yield_output(
                            f"  ✓ Overlaid {orig.get('type','?')} cue {tf_cue['id']}"
                        )
                    else:
                        errors.append(f"Step 4 cue {tf_cue['id']}: {res.stderr[:150]}")
                        await ctx.yield_output(
                            f"  [WARN] Cue {tf_cue['id']} overlay failed: {res.stderr[:150]}"
                        )

                if current != episode_speech_path:
                    with_music = _state.mix_dir / "episode_with_music.mp3"
                    current.rename(with_music)
                    mix_input = with_music
                    await ctx.yield_output(
                        f"  ✓ Music mix complete → {with_music.relative_to(WORKSPACE)}"
                    )
                continue
            # ─────────────────────────────────────────────────────────────────

            # ── Step 5 override: normalise correct input ───────────────────────
            if step_num == 5 and "normalize" in step_desc.lower():
                final_output = plan.get("final_output", "episode_preview.mp3")
                final_path = (
                    WORKSPACE / final_output
                    if final_output.startswith("output/")
                    else _state.mix_dir / Path(final_output).name
                )
                if not mix_input.exists():
                    await ctx.yield_output(
                        f"  [WARN] Input for normalisation not found ({mix_input.name}) — skipping"
                    )
                    continue
                norm_cmd = (
                    f'ffmpeg -y -i "{mix_input}" '
                    f'-af loudnorm=I=-16:TP=-1.5:LRA=11 -ac 1 "{final_path}"'
                )
                res = subprocess.run(
                    norm_cmd, shell=True, capture_output=True,
                    text=True, cwd=str(WORKSPACE), timeout=180,
                )
                if res.returncode == 0:
                    await ctx.yield_output(
                        f"  ✓ Normalised preview: {final_path.relative_to(WORKSPACE)}"
                    )
                else:
                    errors.append(f"Step 5 normalise: {res.stderr[:200]}")
                    await ctx.yield_output(f"  [WARN] Normalisation failed:\n  {res.stderr[:200]}")
                continue
            # ─────────────────────────────────────────────────────────────────

            # Default: run the AI-generated commands verbatim (steps 1, 2, …)
            for cmd in commands:
                try:
                    result = subprocess.run(
                        cmd, shell=True, capture_output=True, text=True,
                        cwd=str(WORKSPACE), timeout=120,
                    )
                    if result.returncode != 0:
                        errors.append(f"Step {step_num}: {cmd}\n  → {result.stderr[:200]}")
                        await ctx.yield_output(
                            f"  [WARN] Command failed (exit {result.returncode}):\n"
                            f"  {cmd}\n  {result.stderr[:200]}"
                        )
                    else:
                        await ctx.yield_output(f"  ✓ {cmd[:80]}…")
                except subprocess.TimeoutExpired:
                    errors.append(f"Step {step_num}: {cmd} — timed out")
                    await ctx.yield_output(f"  [WARN] Command timed out: {cmd[:80]}")

        final_output = plan.get("final_output", "episode_preview.mp3")
        final_path = (
            WORKSPACE / final_output
            if final_output.startswith("output/")
            else _state.mix_dir / Path(final_output).name
        )

        # Build transcript-with-files artifact
        ts_with_files = plan.get("transcript_with_files", {})
        tf_path = _state.mix_dir / "transcript-with-files.json"
        tf_path.write_text(json.dumps(ts_with_files, indent=2))

        summary_lines = [
            "Audio Production Workflow complete!\n",
            f"  Episode:          {_state.episode_dir.name}",
            f"  Model:            {_state.model}",
            f"  Script:           {_state.script_path.relative_to(WORKSPACE)}",
            f"  Music plan:       {(_state.scripts_dir / 'music-plan.json').relative_to(WORKSPACE)}",
            f"  Timestamped tx:   {(_state.mix_dir / 'timestamped-transcript.json').relative_to(WORKSPACE)}",
            f"  Mix plan:         {plan_path.relative_to(WORKSPACE)}",
            f"  Tx with files:    {tf_path.relative_to(WORKSPACE)}",
        ]
        if final_path.exists():
            summary_lines.append(f"  Preview audio:    {final_path.relative_to(WORKSPACE)}")
        else:
            summary_lines.append(
                f"  Preview audio:    {final_output} (not generated — see warnings)"
            )

        if errors:
            summary_lines += ["", f"  Warnings ({len(errors)}):"]
            for e in errors[:5]:
                summary_lines.append(f"    {e}")

        await ctx.yield_output("\n".join(summary_lines))


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_section(text: str, open_tag: str, close_tag: str) -> str:
    """Extract content between two delimiter tags."""
    pattern = re.escape(open_tag) + r"(.*?)" + re.escape(close_tag)
    match = re.search(pattern, text, re.DOTALL)
    return match.group(1) if match else ""


# ── Build the workflow ────────────────────────────────────────────────────────

def build_workflow(slug: str | None = None, model: str | None = None, resume: bool = False):
    ssml_gen_agent  = create_ssml_voice_generator(SHOW_CONTEXT)
    vv_gen_agent    = create_vibe_voice_generator(SHOW_CONTEXT)
    music_dir_agent = create_music_director(SHOW_CONTEXT)
    audio_tech_agent = create_audio_technician(SHOW_CONTEXT)
    audio_mix_agent  = create_audio_mixer(SHOW_CONTEXT)

    # The voice generator choice is made at runtime (stored in _state.model),
    # but we still need an executor wired for each path. The VoiceGenRouter
    # inspects _state.model and routes accordingly.
    ssml_exec    = AgentExecutor(agent=ssml_gen_agent,   id="ssml_gen")
    vv_exec      = AgentExecutor(agent=vv_gen_agent,     id="vv_gen")
    music_exec   = AgentExecutor(agent=music_dir_agent,  id="music_director")
    tech_exec    = AgentExecutor(agent=audio_tech_agent, id="audio_tech")
    mixer_exec   = AgentExecutor(agent=audio_mix_agent,  id="audio_mixer")

    # The voice gen executor changes per model — we register both and use
    # a VoiceGenFanOut router to select the right one.
    class VoiceGenFanOut(Executor):
        """Routes to SSML generator (mai-2) or VibeVoice generator."""

        def __init__(self, id: str):
            super().__init__(id=id)

        @handler
        async def route(self, request: AgentExecutorRequest, ctx: WorkflowContext) -> None:
            target = "ssml_gen" if _state.model == "mai-2" else "vv_gen"
            await ctx.send_message(request, target_id=target)

    class AudioGenDispatch(Executor):
        """Routes to MAI-2 executor or VibeVoice HITL based on _state.model."""

        def __init__(self, id: str):
            super().__init__(id=id)

        @handler
        async def route(self, request: AgentExecutorRequest, ctx: WorkflowContext) -> None:
            target = "mai2_audio" if _state.model == "mai-2" else "vv_hitl"
            await ctx.send_message(request, target_id=target)

    audio_gen_dispatch = AudioGenDispatch("audio_gen_dispatch")

    loader          = TranscriptLoaderExecutor(
        "loader", "voice_gen_fanout", "music_director", slug=slug, model=model, resume=resume
    )
    script_save     = ScriptSaveExecutor("script_save", "audio_gen_dispatch",
                                         model or "")
    music_plan_save = MusicPlanSaveExecutor("music_plan_save", "audio_tech_fan_in")
    mai2_audio      = MAI2AudioExecutor("mai2_audio", "whisper")
    vv_hitl         = VibeVoiceHITLExecutor("vv_hitl", "whisper")
    whisper         = WhisperExecutor("whisper", "audio_tech_fan_in")
    tech_fan_in     = AudioTechFanIn("audio_tech_fan_in", "audio_tech")
    ts_save         = TimestampedTranscriptSaveExecutor("ts_save", "audio_mixer")
    mix_plan        = MixPlanExecutor("mix_plan")

    return (
        WorkflowBuilder(start_executor=loader)

        # Phase 1: parallel fan-out from transcript loader — both voice gen and
        # music director start in the same superstep.
        .add_edge(loader,            ssml_exec)
        .add_edge(loader,            vv_exec)
        .add_edge(loader,            music_exec)

        # Voice gen path
        .add_edge(ssml_exec,         script_save)
        .add_edge(vv_exec,           script_save)

        # Music director path
        .add_edge(music_exec,        music_plan_save)

        # Phase 2: audio generation (fork by model)
        .add_edge(script_save,       audio_gen_dispatch)
        .add_edge(audio_gen_dispatch, mai2_audio)
        .add_edge(audio_gen_dispatch, vv_hitl)

        # Phase 3: Whisper transcription
        .add_edge(mai2_audio,        whisper)
        .add_edge(vv_hitl,           whisper)

        # Phase 4: fan-in (whisper + music plan) → audio technician
        .add_edge(whisper,           tech_fan_in)
        .add_edge(music_plan_save,   tech_fan_in)
        .add_edge(tech_fan_in,       tech_exec)
        .add_edge(tech_exec,         ts_save)

        # Phase 5: audio mixer → execute mix
        .add_edge(ts_save,           mixer_exec)
        .add_edge(mixer_exec,        mix_plan)

        .build()
    )


def main():
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logger = logging.getLogger(__name__)

    parser = argparse.ArgumentParser(description="Audio Production Workflow")
    parser.add_argument("--episode", type=str, default=None,
                        help="Episode name or slug (partial match OK)")
    parser.add_argument("--model", type=str, default=None,
                        choices=list(VALID_MODELS),
                        help="TTS model: mai-2 or vibe-voice")
    parser.add_argument("--resume", action="store_true",
                        help="Resume from the most advanced existing checkpoint in the episode dir")
    args = parser.parse_args()

    global workflow
    workflow = build_workflow(slug=args.episode, model=args.model, resume=args.resume)

    logger.info("Audio Production Workflow — Section 4")
    logger.info("DevUI: http://localhost:8090")
    if args.episode:
        logger.info(f"Episode: {args.episode}")
    if args.model:
        logger.info(f"Model:   {args.model}")

    from agent_framework_devui import serve
    serve(entities=[workflow], port=8090, auto_open=True,
          instrumentation_enabled=True, auth_enabled=False)


# Module-level workflow (picks most recent episode, no model pre-selected)
workflow = build_workflow()

if __name__ == "__main__":
    main()
