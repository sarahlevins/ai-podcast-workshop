"""Generate MAI-2 voice samples for all English prebuilt voices across multiple speaking styles.

Outputs one .mp3 per (voice × style) combination to a mai-2/ subdirectory alongside this script:
  voice-samples/mai-2/<VoiceName>/

Run from the repo root:
    python content/2-Developing_the_concept/exercise/resources/voice-samples/generate_mai2_samples.py

Reads credentials from environment (or a .env file in the repo root):
    FOUNDRY_REGION  — Azure MAI Voice 2 endpoint URL
    FOUNDRY_API_KEY       — Azure MAI Voice 2 subscription key

Reference: https://learn.microsoft.com/en-us/azure/ai-services/speech-service/mai-voices#prebuilt-voices-1
"""

import os
import sys
import time
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parents[5]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from utils import load_env  # noqa: E402

load_env()

REGION = os.getenv("FOUNDRY_REGION", "")
KEY = os.getenv("FOUNDRY_API_KEY", "")

OUT_BASE = Path(__file__).parent / "mai-2"

# ── Voice definitions ─────────────────────────────────────────────────────────
# Source: https://learn.microsoft.com/en-us/azure/ai-services/speech-service/mai-voices#prebuilt-voices-1
#
# supported_styles: list of style names this voice accepts, or None for no style support.

VOICES = [
    {
        "name": "Isla",
        "id": "en-AU-Isla:MAI-Voice-2",
        "lang": "en-AU",
        "gender": "female",
        "supported_styles": [
            "angry", "confused", "determined", "disgusted", "embarrassed",
            "excited", "fearful", "happy", "hopeful", "jealous", "joyful",
            "regretful", "relieved", "sad", "shouting", "softvoice",
            "surprised", "whispering",
        ],
    },
    {
        "name": "Ethan",
        "id": "en-US-Ethan:MAI-Voice-2",
        "lang": "en-US",
        "gender": "male",
        "supported_styles": [
            "angry", "confused", "determined", "disgusted", "embarrassed",
            "excited", "fearful", "happy", "hopeful", "jealous", "joyful",
            "regretful", "relieved", "sad", "shouting", "softvoice",
            "surprised", "whispering",
        ],
    },
    {
        "name": "Grant",
        "id": "en-US-Grant:MAI-Voice-2",
        "lang": "en-US",
        "gender": "male",
        "supported_styles": None,  # no expression styles
    },
    {
        "name": "Harper",
        "id": "en-US-Harper:MAI-Voice-2",
        "lang": "en-US",
        "gender": "female",
        "supported_styles": [
            "angry", "confused", "determined", "embarrassed", "excited",
            "happy", "hopeful", "joyful", "regretful", "relieved", "sad",
            "shouting", "softvoice", "whispering",
        ],
    },
    {
        "name": "Iris",
        "id": "en-US-Iris:MAI-Voice-2",
        "lang": "en-US",
        "gender": "female",
        "supported_styles": None,  # no expression styles
    },
    {
        "name": "Jasper",
        "id": "en-US-Jasper:MAI-Voice-2",
        "lang": "en-US",
        "gender": "male",
        "supported_styles": None,  # no expression styles
    },
    {
        "name": "Olivia",
        "id": "en-US-Olivia:MAI-Voice-2",
        "lang": "en-US",
        "gender": "female",
        "supported_styles": [
            "angry", "confused", "determined", "disgusted", "embarrassed",
            "excited", "fearful", "happy", "hopeful", "jealous", "joyful",
            "regretful", "relieved", "sad", "shouting", "softvoice",
            "surprised", "whispering",
        ],
    },
]

# Representative styles for podcast use — a useful cross-section without generating all 18.
# Voices with supported_styles=None get only the neutral sample.
SAMPLE_STYLES = [
    {
        "name": "neutral",
        "style": None,
        "text": "Welcome to the show. Today we're exploring one of the most interesting questions in this space — and I think by the end, you'll see it differently.",
    },
    {
        "name": "happy",
        "style": "happy",
        "text": "I just found something absolutely fascinating about this topic, and I genuinely cannot wait to share it with you. This one surprised me.",
    },
    {
        "name": "joyful",
        "style": "joyful",
        "text": "This is genuinely one of the most delightful discoveries I've made in this field. It completely made my week — and I think it'll make yours too.",
    },
    {
        "name": "excited",
        "style": "excited",
        "text": "Wait — hold on — this is the part where everything clicks into place. Are you ready for this? Because it completely changed how I think about the whole thing.",
    },
    {
        "name": "sad",
        "style": "sad",
        "text": "It's a difficult reality to sit with. And I think acknowledging that honestly — rather than rushing past it — is actually where the important conversation starts.",
    },
    {
        "name": "regretful",
        "style": "regretful",
        "text": "Looking back, I wish we had caught this sooner. There's a real cost to getting it wrong, and I think we owe it to our listeners to name that.",
    },
    {
        "name": "angry",
        "style": "angry",
        "text": "Look, I'll be direct: that reasoning just doesn't hold up, and I think we do everyone a disservice by pretending otherwise. Let me tell you exactly why.",
    },
    {
        "name": "determined",
        "style": "determined",
        "text": "Here's what I know for certain: this matters, and we're going to get to the bottom of it — because our listeners deserve real answers, not comfortable ones.",
    },
    {
        "name": "whispering",
        "style": "whispering",
        "text": "I'm going to tell you something that not a lot of people in this space want to say out loud. And I think once you hear it, you'll understand why.",
    },
]


# ── API helpers ───────────────────────────────────────────────────────────────

def _headers() -> dict:
    return {
        "Content-Type": "application/ssml+xml",
        "X-Microsoft-OutputFormat": "audio-24khz-160kbitrate-mono-mp3",
        "User-Agent": "mai2-sample-generator",
        "Ocp-Apim-Subscription-Key": KEY,
    }


def _build_ssml(voice_id: str, lang: str, text: str, style: str | None) -> str:
    if style:
        inner = (
            f'    <mstts:express-as style="{style}">\n'
            f"      {_escape_xml(text)}\n"
            f"    </mstts:express-as>"
        )
    else:
        inner = f"    {_escape_xml(text)}"

    return (
        f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis"\n'
        f'       xmlns:mstts="http://www.w3.org/2001/mstts" xml:lang="{lang}">\n'
        f'  <voice name="{voice_id}">\n'
        f"{inner}\n"
        "  </voice>\n"
        "</speak>"
    )


def _escape_xml(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def synthesize(voice_id: str, lang: str, text: str, style: str | None, out_path: Path) -> bool:
    """Synthesize to out_path. Returns True on success, False on skippable failure."""
    ssml = _build_ssml(voice_id, lang, text, style)
    url = f"https://{REGION}.tts.speech.microsoft.com/cognitiveservices/v1"
    try:
        resp = requests.post(url, headers=_headers(), data=ssml.encode("utf-8"), timeout=180)
    except requests.RequestException as e:
        print(f"    [network error] {e}")
        return False

    if resp.status_code == 400:
        print(f"    [skipped — 400: {resp.text[:120]!r}]")
        return False

    if not resp.ok:
        print(f"    [error {resp.status_code}] {resp.text[:200]!r}")
        return False

    out_path.write_bytes(resp.content)
    size_kb = len(resp.content) // 1024
    print(f"    ✓ {out_path.name} ({size_kb} KB)")
    return True


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    if not REGION or not KEY:
        sys.exit(
            "Error: FOUNDRY_API_KEY and FOUNDRY_REGION must be set "
            "(in .env or environment)."
        )

    print(f"Output: {OUT_BASE}\n")

    total = 0
    skipped = 0

    for voice in VOICES:
        voice_dir = OUT_BASE / voice["name"]
        voice_dir.mkdir(parents=True, exist_ok=True)
        supported = set(voice["supported_styles"] or [])
        print(f"{voice['name']} ({voice['id']}):")

        for style_def in SAMPLE_STYLES:
            style = style_def["style"]

            # Skip styles this voice doesn't support (neutral always runs)
            if style is not None and style not in supported:
                continue

            out_path = voice_dir / f"{style_def['name']}.mp3"
            if out_path.exists():
                print(f"    — {out_path.name} already exists, skipping")
                skipped += 1
                continue

            ok = synthesize(
                voice_id=voice["id"],
                lang=voice["lang"],
                text=style_def["text"],
                style=style,
                out_path=out_path,
            )
            if ok:
                total += 1
                time.sleep(0.3)  # avoid hammering the API

        print()

    print(f"Done. Generated {total} samples ({skipped} already existed).")
    print(f"Listen at: {OUT_BASE}/")


if __name__ == "__main__":
    main()
