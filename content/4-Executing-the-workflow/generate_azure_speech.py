"""Synthesize an Azure Speech SSML file to a .wav using Azure AI Foundry's TTS API.

Usage:
    python generate_azure_speech.py <ssml_path> <output_dir>

Output filename is derived from the SSML filename with a .wav extension.

Reads credentials from environment (or a .env file in the repo root):
    AZURE_SPEECH_KEY    — Azure Speech resource key
    AZURE_SPEECH_REGION — Azure region, e.g. "eastus2"
"""

import os
import sys
from pathlib import Path

import azure.cognitiveservices.speech as speechsdk
from utils import load_env

def synthesize(ssml_path: Path, out_path: Path) -> None:
    load_env()
    key = os.environ["AZURE_SPEECH_KEY"]
    region = os.environ["AZURE_SPEECH_REGION"]

    ssml = ssml_path.read_text(encoding="utf-8")

    speech_config = speechsdk.SpeechConfig(subscription=key, region=region)
    # Riff48Khz16BitMonoPcm = high-quality WAV; matches what the Foundry portal samples produce.
    speech_config.set_speech_synthesis_output_format(
        speechsdk.SpeechSynthesisOutputFormat.Riff48Khz16BitMonoPcm
    )

    audio_config = speechsdk.audio.AudioOutputConfig(filename=str(out_path))
    synthesizer = speechsdk.SpeechSynthesizer(
        speech_config=speech_config, audio_config=audio_config
    )

    print(f"Synthesizing {ssml_path.name} → {out_path.name}...")
    result = synthesizer.speak_ssml_async(ssml).get()

    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        size = out_path.stat().st_size
        print(f"Done. Wrote {size:,} bytes to {out_path}")
        return

    if result.reason == speechsdk.ResultReason.Canceled:
        details = result.cancellation_details
        msg = f"Synthesis canceled: {details.reason}"
        if details.error_details:
            msg += f"\n  {details.error_details}"
        raise RuntimeError(msg)

    raise RuntimeError(f"Synthesis failed: {result.reason}")


def main() -> None:
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)

    ssml_path = Path(sys.argv[1]).resolve()
    if not ssml_path.exists():
        sys.exit(f"SSML file not found: {ssml_path}")

    out_dir = Path(sys.argv[2]).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / ssml_path.with_suffix(".wav").name

    synthesize(ssml_path, out_path)


if __name__ == "__main__":
    main()
