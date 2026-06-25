import sys
from pathlib import Path

# ── Path & env setup ──────────────────────────────────────────────────────────

WORKSPACE = Path(__file__).resolve().parents[5]
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))
VOICE_SAMPLES_DIR   = Path(__file__).parent / "samples"

# ── Constants ─────────────────────────────────────────────────────────────────────

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

# ── Helpers ─────────────────────────────────────────────────────────────────────

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

# ── Main ─────────────────────────────────────────────────────────────────────

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
    vv_dir = VOICE_SAMPLES_DIR / "vibe-voice"
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
        sample_dir = VOICE_SAMPLES_DIR / "mai-2" / meta["short_name"]
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
        "_resources/voice/samples/voice-samples-guide.md"
    )

    return "\n".join(lines)
