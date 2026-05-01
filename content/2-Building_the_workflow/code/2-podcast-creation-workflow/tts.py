"""
Run VibeVoice TTS on a podcast script file.

Usage:
    python tts.py output/script_20260501_040258_vibevoice.txt episode.wav
    python tts.py output/script_20260501_040258_vibevoice.txt   # saves to episode.wav

The script file must use "Name: dialogue" lines (the _vibevoice.txt files from
the workflow are already in the right format). Speaker names are automatically
mapped to Speaker 0, 1, 2... in order of first appearance.
"""

import re
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
import torch

MODEL_ID = "vibevoice/VibeVoice-1.5B"
SAMPLE_RATE = 24000


def remap_to_speaker_numbers(text: str) -> str:
    """Convert 'Name: line' format to 'Speaker N: line' (0-indexed) for the processor."""
    speaker_map: dict[str, int] = {}
    out_lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            out_lines.append("")
            continue
        # Match any "Word(s): text" pattern
        m = re.match(r"^([A-Za-z][A-Za-z0-9 _-]*):\s*(.+)$", stripped)
        if m:
            name, dialogue = m.group(1).strip(), m.group(2)
            if name not in speaker_map:
                speaker_map[name] = len(speaker_map)
            out_lines.append(f"Speaker {speaker_map[name]}: {dialogue}")
        else:
            out_lines.append(stripped)
    if speaker_map:
        print(f"Speaker mapping: {speaker_map}")
    return "\n".join(out_lines)


def main():
    script_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
        "output/script_20260501_040258_vibevoice.txt"
    )
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("episode.wav")

    if not script_path.exists():
        sys.exit(f"Script file not found: {script_path}")

    raw = script_path.read_text(encoding="utf-8")
    script = remap_to_speaker_numbers(raw)

    print(f"Loading model from cache: {MODEL_ID}")
    from vibevoice.modular.modeling_vibevoice_inference import (
        VibeVoiceForConditionalGenerationInference,
    )
    from vibevoice.processor.vibevoice_processor import VibeVoiceProcessor

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device}")

    processor = VibeVoiceProcessor.from_pretrained(MODEL_ID)
    model = VibeVoiceForConditionalGenerationInference.from_pretrained(
        MODEL_ID,
        torch_dtype=torch.float16,  # halves RAM footprint (~2.6 GB vs ~5.2 GB)
        low_cpu_mem_usage=True,     # load weights in-place, avoids doubling peak RAM
    ).to(device)
    model.eval()

    print("Processing script...")
    inputs = processor(text=script, return_tensors="pt", padding=True)
    inputs = {k: v.to(device) if isinstance(v, torch.Tensor) else v for k, v in inputs.items()}

    print("Generating audio (this will take a while on CPU)...")
    with torch.inference_mode():
        output = model.generate(
            **inputs,
            tokenizer=processor.tokenizer,
            return_speech=True,
        )

    speech_chunks = [chunk for chunk in output.speech_outputs if chunk is not None]
    if not speech_chunks:
        sys.exit("No audio was generated.")

    audio = torch.cat(speech_chunks, dim=-1).squeeze().cpu().float().numpy()
    sf.write(str(out_path), audio, SAMPLE_RATE)
    duration = len(audio) / SAMPLE_RATE
    print(f"Saved {duration:.1f}s of audio to {out_path}")


if __name__ == "__main__":
    main()
