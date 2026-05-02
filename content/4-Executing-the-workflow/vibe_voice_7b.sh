#!/bin/bash

# VibeVoice Audio Generation Script
# This script clones VibeVoice, installs dependencies, and generates audio from podcast text
#
# Usage: ./vibe_voice_7b.sh [TXT_PATH] [SPEAKER_NAMES...]
# Example (7B): ./vibe_voice_7b.sh ./podcast.txt Xinran Anchen

set -e  # Exit on error

MODEL_PATH="vibevoice/VibeVoice-7B"
TXT_PATH="./podcast.txt"
SPEAKER_NAMES=("Xinran" "Anchen")  # demo voices; order maps to speaker 1, speaker 2, ...

while [ $# -gt 0 ]; do
    case "$1" in
        -h|--help)
            echo "Usage: ./vibe_voice_7b.sh [--txt TXT_PATH] [TXT_PATH] [SPEAKER_NAMES...]"
            echo "Example: ./vibe_voice_7b.sh ./script.txt en-Maya_woman en-Alice_woman"
            exit 0
            ;;
        --txt|--txt_path)
            shift
            if [ -z "$1" ] || [[ "$1" == --* ]]; then
                echo "Error: --txt requires a file path argument" >&2
                exit 1
            fi
            TXT_PATH="$1"
            shift
            break
            ;;
        --*)
            echo "Unknown option: $1" >&2
            exit 1
            ;;
        *)
            if [[ "$1" == *.txt ]] || [ -f "$1" ]; then
                TXT_PATH="$1"
                shift
            fi
            break
            ;;
    esac
done

if [ $# -gt 0 ]; then
    SPEAKER_NAMES=("$@")
fi

# Convert a relative text path to an absolute path before changing directories.
if [[ "$TXT_PATH" != /* ]]; then
    TXT_PATH="$(cd "$(dirname "$TXT_PATH")" && pwd)/$(basename "$TXT_PATH")"
fi

if [ ! -f "$TXT_PATH" ]; then
    echo "Error: txt file not found: $TXT_PATH" >&2
    exit 1
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