#!/bin/bash

# VibeVoice Audio Generation Script
# This script clones VibeVoice, installs dependencies, and generates audio from podcast text
#
# Usage: ./vibe_voice_7b.sh [MODEL_PATH] [TXT_PATH] [SPEAKER_NAMES...]
# Example (1.5B): ./vibe_voice_7b.sh vibevoice/VibeVoice-1.5B ../03.Application/podcast.txt Xinran Anchen

set -e  # Exit on error

MODEL_PATH="${1:-vibevoice/VibeVoice-7B}"
TXT_PATH="${2:-./podcast.txt}"
if [ $# -ge 2 ]; then shift 2; fi
if [ $# -eq 0 ]; then
    SPEAKER_NAMES=("Xinran" "Anchen")  # demo voices; order maps to speaker 1, speaker 2, ...
else
    SPEAKER_NAMES=("$@")
fi

echo "Step 1: Cloning VibeVoice repository..."
if [ ! -d "VibeVoice" ]; then
    git clone https://github.com/vibevoice-community/VibeVoice.git
else
    echo "VibeVoice directory already exists, skipping clone."
fi

echo "Step 2: Installing dependencies..."
cd VibeVoice/
uv pip install -e .

echo "Step 3: Generating audio from podcast text (model=${MODEL_PATH})..."
python demo/inference_from_file.py \
    --model_path "${MODEL_PATH}" \
    --txt_path "${TXT_PATH}" \
    --speaker_names ${SPEAKER_NAMES[@]}

echo "Audio generation complete!"