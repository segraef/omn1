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

**omn1** is your own AI hub: every model on OpenRouter at the best rate, switch any time, and one web UI for text, images, video, music and read-aloud (images, video and music from every model via [add-ons](addons/)). The same key works in VS Code as **omn1 Code**. Built on [Open WebUI](https://github.com/open-webui/open-webui).

<p align="center">
  <img src="assets/diagram.svg" alt="What is omn1: one app per AI (chaos) versus every model in one chat (order)" width="100%" />
</p>

<p align="center">
  <img src="assets/demo.gif" alt="omn1 demo: Claude, GPT-6, DeepSeek and Qwen in one chat, then a picture, a video and a local model" width="100%" />
</p>

## Quick start

```bash
docker compose up -d
```

## Local models (optional)

Install [Ollama](https://ollama.com/download), then pull a model:

```bash
ollama pull huihui_ai/qwen3-abliterated:8b
```

MIT licensed. See [`LICENSE`](LICENSE).
