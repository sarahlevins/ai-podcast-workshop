# Executing the Workflow (15 minutes)

## Plug in your agent artefacts

Update the agent instructions with the host personalities and workflow definitions you created in the previous section.

## Run the full pipeline

### 1. Launch the workflow

```bash
python code/02.Workflow-MultiAgent/02.WorkflowDevUI/main.py
```

### 2. Submit a topic

Enter a topic for your podcast episode. The pipeline will:

1. **Research** the topic using web search
2. **Generate a script** with your defined host personalities
3. **Present the script** for your review

### 3. Review the script

- Type **"yes"** to approve the script
- Type anything else to reject it with feedback — the script agent will regenerate based on your notes

The approval loop continues until you're happy with the result.

### 4. Generate audio

Once approved, the script is saved to a file. Generate audio from it:

```bash
cd code/03.GenerationAudio
./run_vibe_voice.sh
```

#### Why VibeVoice-1.5B?

VibeVoice is an open-source text-to-speech framework designed for expressive, long-form, multi-speaker audio like podcasts. It uses an autoregressive LLM combined with a diffusion head to generate speech from continuous tokens at an ultra-low 7.5 Hz frame rate — keeping output high-fidelity while staying computationally efficient.

Three model sizes are available:

| Model | Params | Max length | Speakers |
|-------|--------|------------|----------|
| VibeVoice-Streaming-0.5B | 0.5B | Real-time | 1 |
| **VibeVoice-1.5B** | **1.5B** | **~90 min** | **Up to 4** |
| VibeVoice-7B | 7B | ~45 min | Up to 4 |

In this workshop we use the **1.5B model**. The 7B model produces higher-quality output but its weights are roughly 14 GB and it needs 16+ GB of VRAM — more than the GPU available in a GitHub Codespace. The 1.5B model fits comfortably in the Codespace environment (~3 GB weights, ~6-8 GB VRAM) while still supporting up to 4 distinct speakers and generating up to 90 minutes of audio, which is more than enough for our podcast episodes. The 0.5B streaming model is even lighter, but it only supports a single speaker, so it can't produce the multi-host conversations we need.

The source code for VibeVoice itself is under 1 MB — the model weights are downloaded from Hugging Face on first run.

### 5. Listen to the results

Your AI-produced podcast episode is ready. Listen to the generated audio and reflect on:

- Did the hosts sound distinct?
- Was the pacing natural?
- What would you change in the agent instructions to improve it?
