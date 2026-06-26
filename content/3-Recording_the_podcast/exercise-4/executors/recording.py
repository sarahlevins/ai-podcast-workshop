"""Recording session executors for podcast-recording.py.

Phases:
  1. RecordingBriefExecutor   — Producer opens the session and briefs the hosts.
  2. RecordingSessionExecutor — Manages the host conversation loop:
                                  a. Calls the next speaker for one utterance.
                                  b. Calls the listener for an immediate reaction.
                                  c. Checks with the Producer every N utterances.
  3. TranscriptAssemblyExecutor — Sends the raw recording log to the Transcript
                                   Assembler and saves the resulting JSON.
"""

import json
import re
from dataclasses import dataclass, field

from agent_framework import (
    AgentExecutorRequest,
    AgentExecutorResponse,
    Executor,
    Message,
    WorkflowContext,
    handler,
)

from .state import (
    EpisodeBriefInput,
    WORKSPACE,
    _log_artifact,
    _run_logger,
    _start_run_logging,
    _state,
    make_episode_dir,
)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_kv_block(text: str, open_tag: str) -> dict:
    """Parse key: value lines from a tagged block (open_tag … ---END---)."""
    m = re.search(rf"{re.escape(open_tag)}(.*?)---END---", text, re.DOTALL)
    if not m:
        return {}
    result = {}
    for line in m.group(1).strip().splitlines():
        line = line.strip()
        if ": " in line:
            key, _, val = line.partition(": ")
            result[key.strip()] = val.strip().strip('"')
    return result


def _append_utterance(uid: str, entry: dict) -> None:
    """Append one utterance entry to utterances.json, creating it if needed."""
    if not _run_logger.run_log_dir:
        return
    path = _run_logger.run_log_dir / "recording" / "utterances.json"
    data = json.loads(path.read_text()) if path.exists() else {}
    data[uid] = entry
    path.write_text(json.dumps(data, indent=2))


# ── Recording-specific state ──────────────────────────────────────────────────

@dataclass
class RecordingState:
    brief: str = ""
    research_notes: str = ""
    # Full text of the producer's opening brief (kept separate, not in recording_log)
    producer_brief_text: str = ""
    # Raw ordered log of host ---UTTERANCE--- blocks only (no producer entries)
    recording_log: list[str] = field(default_factory=list)
    # Current segment name (set from the producer brief)
    current_segment: str = "Cold Open"
    # Utterances produced in the current segment
    turns_in_segment: int = 0
    # Soft turn limit for the current segment (set by producer brief)
    soft_turn_limit: int = 3
    # Ordered list of segment dicts parsed from the producer brief
    segments: list[dict] = field(default_factory=list)
    current_segment_idx: int = 0
    # Whether the producer has signalled the session is complete
    session_done: bool = False
    # Total utterances recorded
    utterance_count: int = 0
    # How often (in utterances) to check in with the producer
    PRODUCER_CHECK_INTERVAL: int = 3
    # Per-host compact research digest (host_id → digest text)
    host_digests: dict = field(default_factory=dict)
    # Rolling summary of covered topics/segments produced by the producer at check-ins
    session_summary: str = ""
    # Target episode duration in minutes, parsed from show_context.md
    target_duration_minutes: float = 5.0


_rec = RecordingState()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_context(system_note: str = "", host_id: str = "") -> str:
    """Return conversation context for a model call.

    Research: shows the host's personal digest if available, otherwise falls
    back to the full research notes (before digests have been generated).
    Once digests exist the producer and assembler see neither — they have the
    brief and full log respectively through other channels.

    History: only the last 10 utterances to cap input-token growth.
    A producer-generated session summary fills the gap for older context.
    """
    recent_log = _rec.recording_log[-10:]

    if len(recent_log) > 1:
        earlier = "\n\n".join(recent_log[:-1])
        log_text = f"### Earlier in this segment\n{earlier}\n\n### Most recent utterance\n{recent_log[-1]}"
    elif recent_log:
        log_text = f"### Most recent utterance\n{recent_log[0]}"
    else:
        log_text = "(nothing yet)"

    lines = [f"Episode brief: {_rec.brief}"]

    if host_id and host_id in _rec.host_digests:
        lines += ["", "## Your Research Notes", _rec.host_digests[host_id]]
    elif not _rec.host_digests and _rec.research_notes:
        # Digests not yet generated (early phases) — show full research notes
        lines += ["", "## Research Notes", _rec.research_notes]

    if _rec.producer_brief_text:
        lines += ["", "## Producer Brief", _rec.producer_brief_text]

    if _rec.session_summary:
        lines += ["", "## Session So Far", _rec.session_summary]

    lines += [
        "",
        f"Current segment: {_rec.current_segment}",
        "",
        "## Recent Conversation",
        log_text,
    ]
    if system_note:
        lines += ["", "## Note", system_note]
    return "\n".join(lines)


def _parse_producer_brief(text: str) -> None:
    """Extract segment list and soft_turn_limit from a PRODUCER-BRIEF block."""
    brief_match = re.search(r"---PRODUCER-BRIEF---(.*?)---END---", text, re.DOTALL)
    if not brief_match:
        return
    content = brief_match.group(1)

    # Split on each "- name:" entry so soft_turn_limit is parsed within its own segment block.
    segments = []
    for seg_block in re.split(r"\n(?=\s*- name:)", content):
        name_match = re.search(r"- name:\s*(.+)", seg_block)
        if not name_match:
            continue
        limit_match = re.search(r"soft_turn_limit:\s*(\d+)", seg_block)
        segments.append({
            "name": name_match.group(1).strip(),
            "soft_turn_limit": int(limit_match.group(1)) if limit_match else 3,
        })

    if segments:
        _rec.segments = segments
        _rec.current_segment = segments[0]["name"]
        _rec.soft_turn_limit = segments[0].get("soft_turn_limit", 3)


def _advance_segment() -> bool:
    """Move to the next segment. Returns False if we were already on the last one."""
    _rec.current_segment_idx += 1
    if _rec.current_segment_idx >= len(_rec.segments):
        return False
    seg = _rec.segments[_rec.current_segment_idx]
    _rec.current_segment = seg["name"]
    _rec.soft_turn_limit = seg.get("soft_turn_limit", 3)
    _rec.turns_in_segment = 0
    return True


# Conversational podcast speech averages ~130 words/minute including natural pauses.
_WORDS_PER_MINUTE = 130


def _timing_summary() -> str:
    """Return a one-line timing status string for the producer check-in.

    Counts words in the text field of every logged utterance, converts to
    minutes at _WORDS_PER_MINUTE, and reports elapsed vs target vs remaining.
    """
    total_words = 0
    for entry in _rec.recording_log:
        m = re.search(r'text:\s*"(.*)"', entry)  # greedy — handles internal quotes
        if m:
            total_words += len(m.group(1).split())

    elapsed = total_words / _WORDS_PER_MINUTE
    target = _rec.target_duration_minutes
    remaining = max(0.0, target - elapsed)

    elapsed_str = f"{int(elapsed)}:{int((elapsed % 1) * 60):02d}"
    target_str = f"{int(target)}:00"
    remaining_str = f"{int(remaining)}:{int((remaining % 1) * 60):02d}"

    urgency = ""
    if remaining <= 0:
        urgency = " ⚠ OVER TIME — wrap up immediately."
    elif remaining < 1.0:
        urgency = " ⚠ Under 1 minute left — begin outro."

    return (
        f"Estimated time: ~{elapsed_str} elapsed / {target_str} target / "
        f"~{remaining_str} remaining.{urgency}"
    )


# ── Executors ─────────────────────────────────────────────────────────────────

class RecordingResearchExecutor(Executor):
    """Phase 0: Researcher researches the topic before the recording session.

    This is the workflow entry point. It initialises all shared state,
    starts run logging, then calls the Researcher agent.
    """

    def __init__(self, id: str, researcher_id: str):
        super().__init__(id=id)
        self._researcher_id = researcher_id

    @handler
    async def start(self, request: EpisodeBriefInput, ctx: WorkflowContext[AgentExecutorRequest]) -> None:
        _rec.brief = request.brief or _state.cli_brief
        _state.brief = _rec.brief
        _state.episode_dir = make_episode_dir(_rec.brief)
        _rec.recording_log = []
        _rec.research_notes = ""
        _rec.producer_brief_text = ""
        _rec.utterance_count = 0
        _rec.current_segment_idx = 0
        _rec.session_done = False
        _rec.host_digests = {}
        _rec.session_summary = ""

        # Parse target duration from show context (e.g. "~5 minutes per episode")
        try:
            show_text = SHOW_CONTEXT_PATH.read_text()
            m = re.search(r"~?(\d+(?:\.\d+)?)\s*min", show_text, re.IGNORECASE)
            _rec.target_duration_minutes = float(m.group(1)) if m else 5.0
        except Exception:
            _rec.target_duration_minutes = 5.0

        _start_run_logging()
        if _run_logger.run_log_dir:
            (_run_logger.run_log_dir / "recording").mkdir(parents=True, exist_ok=True)
        _run_logger.info("research phase — brief: %r", _rec.brief[:60])

        await ctx.send_message(
            AgentExecutorRequest(
                messages=[Message(
                    role="user",
                    contents=[
                        f"Research this episode topic for a podcast recording session:\n\n{_rec.brief}\n\n"
                        "Provide thorough research notes covering key facts, angles, talking points, "
                        "and interesting stories the hosts can draw on during the live recording."
                    ],
                )],
                should_respond=True,
            ),
            target_id=self._researcher_id,
        )


class RecordingResearchRelay(Executor):
    """Receives researcher notes, stores them in _rec, then fans out to all host digest executors."""

    def __init__(self, id: str, host_digest_ids: list[str]):
        super().__init__(id=id)
        self._host_digest_ids = host_digest_ids

    @handler
    async def relay(self, response: AgentExecutorResponse, ctx: WorkflowContext[EpisodeBriefInput]) -> None:
        _rec.research_notes = response.agent_response.text.strip()
        _log_artifact("recording/research_notes.md", _rec.research_notes)
        _run_logger.info("research complete — %d chars, fanning out to %d hosts", len(_rec.research_notes), len(self._host_digest_ids))

        for digest_id in self._host_digest_ids:
            await ctx.send_message(
                EpisodeBriefInput(brief=_rec.brief),
                target_id=digest_id,
            )


class RecordingBriefExecutor(Executor):
    """Phase 1: Producer opens the session.

    Receives the episode brief (after research is done), calls the Recording
    Producer to produce the segment rundown and opening question.
    """

    def __init__(self, id: str, producer_id: str, session_id: str):
        super().__init__(id=id)
        self._producer_id = producer_id
        self._session_id = session_id

    @handler
    async def open_session(self, request: EpisodeBriefInput, ctx: WorkflowContext[AgentExecutorRequest]) -> None:
        # State was initialised in RecordingResearchExecutor; _rec.brief and
        # _rec.research_notes are already populated.
        _run_logger.info("producer brief phase — brief: %r", _rec.brief[:60])

        await ctx.send_message(
            AgentExecutorRequest(
                messages=[Message(
                    role="user",
                    contents=[
                        f"Episode brief:\n\n{_rec.brief}\n\n"
                        f"Research notes:\n\n{_rec.research_notes}\n\n"
                        "Open the recording session. Produce the segment rundown and the opening question. "
                        "Draw on the research notes to give the hosts useful context and talking points."
                    ],
                )],
                should_respond=True,
            ),
            target_id=self._producer_id,
        )


@dataclass
class RecordingTurn:
    """Sent from RecordingBriefRelay → ChatRoomExecutor to kick off the session."""
    context: str
    speaking_host_id: str
    listening_host_id: str


@dataclass
class HostUtterance:
    """A host utterance, tagged with which host sent it, forwarded by HostRelay."""
    host_id: str
    text: str


@dataclass
class ProducerDirection:
    """The producer's response to a mid-session check-in, forwarded by ChatRoomProducerRelay."""
    text: str


class RecordingBriefRelay(Executor):
    """Receives the Producer's opening brief, logs it, then starts the ChatRoom."""

    def __init__(self, id: str, chatroom_id: str, host_ids: list[str]):
        super().__init__(id=id)
        self._chatroom_id = chatroom_id
        self._host_ids = host_ids  # [host_a_id, host_b_id]

    @handler
    async def relay(self, response: AgentExecutorResponse, ctx: WorkflowContext[RecordingTurn]) -> None:
        brief_text = response.agent_response.text
        _rec.producer_brief_text = brief_text  # stored for context, NOT added to recording_log
        _parse_producer_brief(brief_text)
        _log_artifact("recording/producer_brief.md", brief_text)
        _run_logger.info("producer brief received — %d segments", len(_rec.segments))

        await ctx.send_message(
            RecordingTurn(
                context=_build_context(
                    f"The producer has just briefed you (see Producer Brief above). "
                    f"Begin the first segment: {_rec.current_segment}. "
                    "Pick up the opening question from the producer brief and start the conversation."
                ),
                speaking_host_id=self._host_ids[0],
                listening_host_id=self._host_ids[1],
            ),
            target_id=self._chatroom_id,
        )


class HostResearchDigestExecutor(Executor):
    """Phase 0.5: Asks a host agent to distil the research into a personal compact digest.

    Runs once per host before the producer brief so that each host enters the
    recording loop with only the research angles that resonate with them, rather
    than the full (large) research notes on every turn.
    """

    def __init__(self, id: str, host_id: str, host_name: str, agent_exec_id: str):
        super().__init__(id=id)
        self._host_id = host_id
        self._host_name = host_name
        self._agent_exec_id = agent_exec_id

    @handler
    async def digest(self, request: EpisodeBriefInput, ctx: WorkflowContext[AgentExecutorRequest]) -> None:
        _run_logger.info("host digest phase — %r", self._host_name)
        await ctx.send_message(
            AgentExecutorRequest(
                messages=[Message(
                    role="user",
                    contents=[
                        f"You are about to record a podcast episode on: {_rec.brief}\n\n"
                        f"Research notes:\n\n{_rec.research_notes}\n\n"
                        "From your perspective as a host, extract only the points and angles that resonate "
                        "most with your voice and style. Produce a compact personal digest (short bullets) covering:\n"
                        "- Talking points and angles that feel most natural to you\n"
                        "- Specific facts, moments, or quotes you want to draw on\n"
                        "- Phrases or framings that could make strong callbacks\n"
                        "Keep it tight — this is your personal reference card for the session."
                    ],
                )],
                should_respond=True,
            ),
            target_id=self._agent_exec_id,
        )


class HostResearchDigestRelay(Executor):
    """Stores a host's research digest in shared state, then forwards to the next phase."""

    def __init__(self, id: str, host_id: str, next_id: str):
        super().__init__(id=id)
        self._host_id = host_id
        self._next_id = next_id

    @handler
    async def relay(self, response: AgentExecutorResponse, ctx: WorkflowContext[EpisodeBriefInput]) -> None:
        digest = response.agent_response.text.strip()
        _rec.host_digests[self._host_id] = digest
        _log_artifact(f"recording/digest_{self._host_id}.md", digest)
        _run_logger.info("digest stored — host %r, %d chars", self._host_id, len(digest))
        await ctx.send_message(
            EpisodeBriefInput(brief=_rec.brief),
            target_id=self._next_id,
        )


class HostDigestFanIn(Executor):
    """Collects host digests from parallel digest relays and fires once all are done."""

    def __init__(self, id: str, host_count: int, brief_exec_id: str):
        super().__init__(id=id)
        self._host_count = host_count
        self._brief_exec_id = brief_exec_id
        self._completed = 0

    @handler
    async def collect(self, request: EpisodeBriefInput, ctx: WorkflowContext[EpisodeBriefInput]) -> None:
        self._completed += 1
        _run_logger.info("digest fan-in — %d/%d complete", self._completed, self._host_count)
        if self._completed >= self._host_count:
            self._completed = 0
            await ctx.send_message(
                EpisodeBriefInput(brief=_rec.brief),
                target_id=self._brief_exec_id,
            )


class HostRelay(Executor):
    """Wraps an AgentExecutorResponse from a host into a HostUtterance for the ChatRoom.

    One instance per host — lets both hosts share the same target type without a
    duplicate-handler clash in ChatRoomExecutor.
    """

    def __init__(self, id: str, host_id: str, chatroom_id: str):
        super().__init__(id=id)
        self._host_id = host_id
        self._chatroom_id = chatroom_id

    @handler
    async def relay(self, response: AgentExecutorResponse, ctx: WorkflowContext[HostUtterance]) -> None:
        await ctx.send_message(
            HostUtterance(host_id=self._host_id, text=response.agent_response.text.strip()),
            target_id=self._chatroom_id,
        )


class ChatRoomProducerRelay(Executor):
    """Wraps an AgentExecutorResponse from the producer into a ProducerDirection for the ChatRoom."""

    def __init__(self, id: str, chatroom_id: str):
        super().__init__(id=id)
        self._chatroom_id = chatroom_id

    @handler
    async def relay(self, response: AgentExecutorResponse, ctx: WorkflowContext[ProducerDirection]) -> None:
        await ctx.send_message(
            ProducerDirection(text=response.agent_response.text.strip()),
            target_id=self._chatroom_id,
        )


class ChatRoomExecutor(Executor):
    """Group-chat orchestrator for the live recording session.

    Receives typed messages from host relays and the producer relay:
      - RecordingTurn  → kick off the first host (called once from RecordingBriefRelay)
      - HostUtterance  → log it, send reaction prompt to the other host.
                         After reaction, alternate speaker or check in with producer.
      - ProducerDirection → CONTINUE / TRANSITION / DONE

    No self-routing — all messages flow to distinct executor IDs.
    """

    def __init__(
        self,
        id: str,
        host_a_id: str,
        host_b_id: str,
        host_a_name: str,
        host_b_name: str,
        producer_checkin_id: str,
        assembly_id: str,
    ):
        super().__init__(id=id)
        self._host_a_id = host_a_id
        self._host_b_id = host_b_id
        self._host_a_name = host_a_name
        self._host_b_name = host_b_name
        self._producer_checkin_id = producer_checkin_id
        self._assembly_id = assembly_id
        # True while we're waiting for a reaction (vs. a speech turn)
        self._reaction_pending: bool = False
        # Who speaks next — stored when we pause to check in with the producer
        self._next_speaker: str = ""
        self._next_listener: str = ""
        # False until the producer has given the opening roll-in direction
        self._session_started: bool = False

    def _other_host(self, host_id: str) -> str:
        return self._host_b_id if host_id == self._host_a_id else self._host_a_id

    def _host_name(self, host_id: str) -> str:
        return self._host_a_name if host_id == self._host_a_id else self._host_b_name

    def _speech_request(self, note: str = "", host_id: str = "", last_utterance: str = "") -> AgentExecutorRequest:
        if last_utterance:
            other_name = self._host_a_name if host_id == self._host_b_id else self._host_b_name
            respond_note = (
                f"Your co-host {other_name} just said:\n\"{last_utterance}\"\n\n"
                "Respond to that specifically — answer their question, build on their point, "
                "or push back. Don't introduce a new topic until you've engaged with what they said."
            )
            note = (respond_note + "\n\n" + note).strip() if note else respond_note
        return AgentExecutorRequest(
            messages=[Message(role="user", contents=[_build_context(note, host_id=host_id)])],
            should_respond=True,
        )

    def _reaction_request(self, host_id: str = "") -> AgentExecutorRequest:
        prompt = (
            _build_context(host_id=host_id)
            + "\n\nThe host just spoke. React immediately if something prompts a reaction "
            "— an interjection, a backchannel, a laugh, a gasp. "
            "If you have nothing to add right now, output:\n\n"
            "---UTTERANCE---\ntype: backchannel\ntext: \"\"\n---END---"
        )
        return AgentExecutorRequest(
            messages=[Message(role="user", contents=[prompt])],
            should_respond=True,
        )

    @handler
    async def start(self, turn: RecordingTurn, ctx: WorkflowContext[AgentExecutorRequest]) -> None:
        """Ask the producer for a brief roll-in direction, then kick off the first host."""
        self._reaction_pending = False
        self._session_started = False
        self._next_speaker = turn.speaking_host_id
        self._next_listener = turn.listening_host_id
        await ctx.send_message(
            AgentExecutorRequest(
                messages=[Message(
                    role="user",
                    contents=[
                        turn.context
                        + "\n\n## Task\n"
                        "Open the recording session. In your own voice, as if speaking directly to the "
                        "hosts in the studio, give them their opening direction. This should cover:\n"
                        "1. A welcome cue — tell the first host to welcome the listeners and introduce "
                        "the show and this episode's topic.\n"
                        "2. The opening question or angle from your brief to kick off the Cold Open.\n\n"
                        "Do not use ---PRODUCER-BRIEF--- or CONTINUE format — use the ---PRODUCER--- block "
                        "with action: REDIRECT."
                    ],
                )],
                should_respond=True,
            ),
            target_id=self._producer_checkin_id,
        )

    @handler
    async def handle_host(self, msg: HostUtterance, ctx: WorkflowContext) -> None:
        """Receive a host utterance, log it, dispatch the next turn."""
        utterance_text = msg.text
        is_empty_backchannel = (
            "type: backchannel" in utterance_text and 'text: ""' in utterance_text
        )

        if not is_empty_backchannel:
            # Inject the speaker name into the utterance block for the transcript assembler
            speaker_name = self._host_name(msg.host_id)
            utterance_text = utterance_text.replace(
                "---UTTERANCE---",
                f"---UTTERANCE---\nspeaker: {speaker_name}",
                1,
            )
            _rec.recording_log.append(utterance_text)
            _rec.utterance_count += 1
            _rec.turns_in_segment += 1
            uid = f"u{_rec.utterance_count:03d}"
            entry = _parse_kv_block(utterance_text, "---UTTERANCE---")
            entry["kind"] = "host"
            entry["segment"] = _rec.current_segment
            _append_utterance(uid, entry)
            _run_logger.info(
                "utterance %d — segment=%r turn=%d",
                _rec.utterance_count, _rec.current_segment, _rec.turns_in_segment,
            )

        other_host = self._other_host(msg.host_id)

        if self._reaction_pending:
            self._reaction_pending = False
            if is_empty_backchannel:
                # Silent pass — the original speaker keeps the floor so they don't
                # answer their own question when the reactor had nothing to add.
                await self._advance(next_speaker=other_host, next_listener=msg.host_id, ctx=ctx)
            else:
                # The reactor said something — they earned the floor.
                await self._advance(next_speaker=msg.host_id, next_listener=other_host, ctx=ctx)
        else:
            # Got a speech utterance. Ask the other host to react.
            self._reaction_pending = True
            await ctx.send_message(self._reaction_request(host_id=other_host), target_id=other_host)

    def _last_utterance_text(self) -> str:
        """Extract the plain text from the most recent log entry."""
        if not _rec.recording_log:
            return ""
        last = _rec.recording_log[-1]
        m = re.search(r'text:\s*"(.*?)"', last, re.DOTALL)
        return m.group(1).strip() if m else ""

    async def _advance(self, next_speaker: str, next_listener: str, ctx: WorkflowContext) -> None:
        """After a reaction: check with producer if due, otherwise send speech turn."""
        if _rec.session_done:
            await self._finish(ctx)
            return

        # Hard stop: if elapsed words exceed 110% of the target duration, end immediately
        # rather than waiting for the producer to (possibly) defer again.
        total_words = 0
        for entry in _rec.recording_log:
            m = re.search(r'text:\s*"(.*)"', entry)
            if m:
                total_words += len(m.group(1).split())
        if total_words / _WORDS_PER_MINUTE >= _rec.target_duration_minutes * 1.1:
            _rec.session_done = True
            _run_logger.info("hard stop — elapsed words %d exceeds 110%% of target", total_words)
            await self._finish(ctx)
            return

        should_check = (
            _rec.utterance_count > 0
            and _rec.utterance_count % _rec.PRODUCER_CHECK_INTERVAL == 0
        ) or _rec.turns_in_segment >= _rec.soft_turn_limit

        if should_check:
            self._next_speaker = next_speaker
            self._next_listener = next_listener
            await ctx.send_message(
                AgentExecutorRequest(
                    messages=[Message(
                        role="user",
                        contents=[_build_context(
                            f"Segment '{_rec.current_segment}' — "
                            f"{_rec.turns_in_segment} utterances in "
                            f"(soft limit: {_rec.soft_turn_limit}). "
                            f"{_timing_summary()} "
                            "Assess the conversation and decide: CONTINUE, TRANSITION, or REDIRECT. "
                            "Also include a ---SESSION-SUMMARY---...---END--- block with: "
                            "segments and topics covered so far, and 2-3 memorable phrases for later callbacks."
                        )],
                    )],
                    should_respond=True,
                ),
                target_id=self._producer_checkin_id,
            )
        else:
            last_text = self._last_utterance_text()
            await ctx.send_message(
                self._speech_request(host_id=next_speaker, last_utterance=last_text),
                target_id=next_speaker,
            )

    @handler
    async def handle_producer(self, direction: ProducerDirection, ctx: WorkflowContext) -> None:
        """Handle producer direction: opening roll-in, CONTINUE, TRANSITION, REDIRECT, or DONE."""
        text = direction.text

        # Extract and store session summary if the producer included one
        summary_match = re.search(r"---SESSION-SUMMARY---(.*?)---END---", text, re.DOTALL)
        if summary_match:
            _rec.session_summary = summary_match.group(1).strip()

        if not self._session_started:
            # First producer message is the opening roll-in — kick off the first host
            self._session_started = True
            _run_logger.info("producer roll-in received — starting first host")
            note = (
                f"Producer (just now, to you in the studio):\n{text}\n\n"
                "Follow the producer's direction. If they tell you to welcome the listeners and "
                "introduce the show, do that — address your audience directly. "
                "Do NOT acknowledge or thank the producer (don't say 'great', 'thanks', or reference "
                "the producer at all). Speak to your listeners, not to the booth."
            )
            await ctx.send_message(
                self._speech_request(note=note, host_id=self._next_speaker),
                target_id=self._next_speaker,
            )
            return

        if "---PRODUCER-DONE---" in text:
            _rec.session_done = True
            await self._finish(ctx)
            return

        if text.strip() == "CONTINUE":
            # Reset turns so we don't re-trigger the soft-limit check every exchange
            _rec.turns_in_segment = 0
            last_text = self._last_utterance_text()
            continue_note = (
                f"[Producer check-in: the conversation is on track — keep going. "
                f"Stay in the '{_rec.current_segment}' segment.]"
            )
            await ctx.send_message(
                self._speech_request(
                    note=continue_note,
                    host_id=self._next_speaker,
                    last_utterance=last_text,
                ),
                target_id=self._next_speaker,
            )
            return

        # TRANSITION or REDIRECT — append to utterances.json, NOT to recording_log
        uid = f"p{_rec.utterance_count:03d}"
        entry = _parse_kv_block(text, "---PRODUCER---")
        entry["kind"] = "producer"
        entry["after_utterance"] = _rec.utterance_count
        _append_utterance(uid, entry)

        if "action: TRANSITION" in text:
            if not _advance_segment():
                _rec.session_done = True
                await self._finish(ctx)
                return
            _run_logger.info("transitioning to segment: %r", _rec.current_segment)
        else:
            # REDIRECT: stay in segment but reset the turn counter for a fresh grace period
            _rec.turns_in_segment = 0

        note = (
            f"Producer direction:\n{text}\n\n"
            "Follow this direction — do NOT address or acknowledge the producer out loud. "
            "Do not say anything like 'great point' or 'thanks'. "
            "Just continue the conversation naturally in the indicated direction."
        )
        await ctx.send_message(
            self._speech_request(note=note, host_id=self._next_speaker),
            target_id=self._next_speaker,
        )

    async def _finish(self, ctx: WorkflowContext) -> None:
        full_log = "\n\n---\n\n".join(_rec.recording_log)
        _run_logger.info("recording complete — %d utterances", _rec.utterance_count)

        log_path = _state.episode_dir / "recording-log.md"
        log_path.write_text(full_log)
        _log_artifact("recording/full_recording_log.md", full_log)

        await ctx.send_message(
            AgentExecutorRequest(
                messages=[Message(
                    role="user",
                    contents=[
                        "Here is the full recording log. Convert it to a podcast transcript "
                        "conforming to utils/podcast-transcript-v1.json.\n\n"
                        f"{full_log}"
                    ],
                )],
                should_respond=True,
            ),
            target_id=self._assembly_id,
        )


class TranscriptAssemblyExecutor(Executor):
    """Receives the Transcript Assembler's JSON output and saves it to disk."""

    @handler
    async def save(self, response: AgentExecutorResponse, ctx: WorkflowContext[None, str]) -> None:
        transcript_json = response.agent_response.text.strip()

        # Strip markdown fences if the model wrapped the output
        if transcript_json.startswith("```"):
            transcript_json = re.sub(r"^```[a-z]*\n?", "", transcript_json)
            transcript_json = re.sub(r"\n?```$", "", transcript_json)

        transcript_path = _state.episode_dir / "transcript.json"
        transcript_path.write_text(transcript_json)
        _log_artifact("recording/transcript.json", transcript_json)
        _run_logger.info("transcript saved: %s", transcript_path.relative_to(WORKSPACE))

        ep = _state.episode_dir.relative_to(WORKSPACE)
        await ctx.yield_output(
            f"Recording complete!\n\n"
            f"  Transcript:    {ep}/transcript.json\n"
            f"  Recording log: {ep}/recording-log.md\n"
            f"  Utterances:    {_rec.utterance_count}\n"
        )
