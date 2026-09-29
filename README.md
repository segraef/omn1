<p align="center">
  <img src="assets/logo.svg" alt="omn1" width="240" />
</p>

<p align="center">
  <strong>One chat to rule them all.</strong>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License: MIT" /></a>
  <img src="https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white" alt="Docker Compose" />
  <img src="https://img.shields.io/badge/Open%20WebUI-v0.11.4-000000" alt="Open WebUI" />
  <img src="https://img.shields.io/badge/OpenRouter-powered-7c3aed" alt="OpenRouter" />
  <a href="https://github.com/segraef/sec-kit"><img src="https://raw.githubusercontent.com/segraef/sec-kit/main/docs/media/badge.svg" alt="Scanned with SecKit" /></a>
</p>

**omn1** is one chat for all AI models. Pick any model, switch any time, and create text, images, video and music, in the cloud through OpenRouter or locally with Ollama. Built on [Open WebUI](https://github.com/open-webui/open-webui).

<p align="center">
  <img src="assets/diagram.svg" alt="What is omn1: one app per AI (chaos) versus every model in one chat through OpenRouter, Requesty, Hugging Face or local models (order)" width="100%" />
</p>

<p align="center">
  <img src="assets/demo.gif" alt="omn1 demo: Claude, GPT-6, DeepSeek and Qwen in one chat, then a picture, a video and a local model" width="100%" />
</p>

## What you need

- An API key from the gateway you prefer: [OpenRouter](https://openrouter.ai/keys), [Requesty](https://requesty.ai), [Hugging Face](https://huggingface.co/settings/tokens) or any other OpenAI-compatible one (add it in omn1 under Admin Panel > Settings > Connections; OpenRouter is set up by default)
- Docker, anywhere: locally on your Mac or PC, or in the cloud on a small VM (Azure, AWS, any provider) or Azure Container Apps (with an Azure Postgres database for the chats)

## Quick start

```bash
docker compose up -d
```

## Local models (optional)

Install [Ollama](https://ollama.com/download), then pull a model:

```bash
ollama pull huihui_ai/qwen3-abliterated:8b
```

Reload omn1 and the model shows up in the model picker next to the OpenRouter models.

## FAQ

**What does omn1 add over OpenRouter's own chat?**

For casual chatting, OpenRouter's chat is plenty. omn1 makes the difference when you want:

1. **Self-hosted:** runs on your machine or in your own cloud, and your chats stay in your own database.
2. **Gateway independence:** not only OpenRouter. Any OpenAI-compatible gateway (Requesty, AIML API, Hugging Face, ...) plugs in as another connection.
3. **Local models:** Ollama models, including abliterated ones, right next to the cloud models.

MIT licensed. See [`LICENSE`](LICENSE).
