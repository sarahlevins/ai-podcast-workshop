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

This uses VibeVoice to transform your text script into multi-speaker audio.

### 5. Listen to the results

Your AI-produced podcast episode is ready. Listen to the generated audio and reflect on:

- Did the hosts sound distinct?
- Was the pacing natural?
- What would you change in the agent instructions to improve it?
