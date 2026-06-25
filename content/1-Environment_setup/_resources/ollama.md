# Ollama Set Up

> ***NOTE: this is not recommended for this workshop, because the download and installation will take some time ***

Hugging Face allows you to download and locally run models. This is great if you don't want your data in the cloud and you don't want any surprise usage bills.

The prebuilt GitHub codespace image for this workshop has `llama3.2:3b` built into it, so if you want to use it - use the Codespace.

If you have ollama installed and models downloaded locally already - great! Use that.

If you want to get set up with Ollama localy for the first time you can run the follwing to install the cli:

```bash
# Install Ollama (also requires zstd for model-blob decompression).
apt-get update \
&& apt-get install -y zstd \
&& rm -rf /var/lib/apt/lists/* \
&& curl -fsSL https://ollama.com/install.sh | sh
```

Then you can download and run models:
```bash
# start the ollama process
ollama serve
# download and run a prompt on the model. The model will be cached locally
# and stay loaded into RAM for 10m
ollama run llama3.2:3b "Hi how are you?" 
```

1. Copy the example .env
```bash
cp .env.example .env
```

2. Edit `.env` to set these values:

```env
MODEL_PROVIDER=ollama
OLLAMA_HOST=http://localhost:11434
OLLAMA_CHAT_MODEL_ID=llama3.2:3b
```
