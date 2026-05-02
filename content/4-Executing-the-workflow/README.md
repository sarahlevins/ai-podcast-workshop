# Generating the audio (20 minutes)

Once approved, the script is saved to a file. Generate audio from it.

To generate the audio we need GPU. That can be limited on most people's machines, so we will look at some ways to do it in the cloud on the cheap.

We are going to go through a few different models to find the right one for our team.

- VibeVoice-1.5B
- VibeVoice-7B
- Azure TTS Dragon HD
- other azure one

## Why VibeVoice?

VibeVoice is an open-source text-to-speech framework designed for expressive, long-form, multi-speaker audio like podcasts. It uses an autoregressive LLM combined with a diffusion head to generate speech from continuous tokens at an ultra-low 7.5 Hz frame rate — keeping output high-fidelity while staying computationally efficient.

Three model sizes are available:

| Model | Params | Max length | Speakers |
|-------|--------|------------|----------|
| VibeVoice-Streaming-0.5B | 0.5B | Real-time | 1 |
| VibeVoice-1.5B | 1.5B | ~90 min | Up to 4 |
| VibeVoice-7B | 7B | ~45 min | Up to 4 |

The source code for VibeVoice itself is under 1 MB — the model weights are downloaded from Hugging Face on first run.

### 1. VibeVoice-1.5B
1. install the Colab extension
2. Open the [vibevoice-1b.ipynb notebook](./vibevoice-1b.ipynb)
3. Select other kernel, then select Colab
4. Create a Colab server. GPU, T4
5. Run the cells to generate your audio

### 2. VibeVoice-7B
1. Go to [lightning.ai](https://lightning.ai/) and sign up
2. Create a A100 GPU machine
3. create a file vibevoice.7b.sh in the workspace
4. paste the contents of [vibevoice-7b.sh](./vibevoice-1b.ipynb) in
5. run `chmod+x vibevoice-7b.sh` in the terminal
6. run `./vibevoice-7b.sh`
7. Wait for your audio to be generated then download

## Why Azure AI Speech

<insert why here>

[Voice Gallery](https://ai.azure.com/explore/models/aiservices/Azure-AI-Speech/version/1/registry/azureml-cogsvc/tryout?tid=54ba0fd2-46b7-46d8-9f55-c1500e37a2c2#voicegallery)

1. Ensure you have an Azure Foundry resource, and your FOUNDRY_API_KEY and FOUNDRY_REASONS environment variables set in `.env`
2. run the following command 

```bash
python /workspace/ai-podcast-workshop/content/3-Generating_the_audio/synthesize_ssml.py
```
