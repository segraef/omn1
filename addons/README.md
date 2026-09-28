# Add-ons

Two optional add-ons that give banana video and music, plus a setting for read-aloud. They all pay through OpenRouter.

| Add-on | What you get |
| --- | --- |
| [`video.py`](video.py) | Veo 3.1, Veo 3.1 Lite and Wan 3.0 in the model picker. Describe a scene, get a video player in the chat after 1 to 3 minutes. |
| [`music.py`](music.py) | Lyria 3 Pro (full songs) and Lyria 3 Clip (30 seconds) in the model picker. Describe a song, get an audio player and the lyrics. |

## Install

1. Admin Panel > Functions > **+**.
2. Paste the whole file, **Save**, then switch it on.
3. The new models show up in the picker. Admins pay with the key already saved under Connections.

Other people pay with their own OpenRouter key. You make the models visible to them (Admin Panel > Settings > Models, open the model, set it to Public). They paste their key under Chat Controls (the sliders icon at the top right of a chat) > Valves > Functions > Banana Video or Banana Music > API Key. Without a key they get a short note telling them where to put one, and nothing is charged.

## Read-aloud

The speaker icon under a reply uses your browser's free voice. For a better voice:

1. Admin Panel > Settings > Audio.
2. Text-to-Speech Engine: **OpenAI**. Open WebUI then fills in `tts-1` and `alloy`. Change them to:
   - Model: `x-ai/grok-voice-tts-1.0`
   - Voice: `eve`
3. Paste your OpenRouter key and save.

API Base URL (`https://openrouter.ai/api/v1`) and Parameters (`{"response_format":"mp3"}`) are already filled in on a fresh install. If not, enter them too.

On a video or song reply, read-aloud also reads out the file address. Open WebUI needs it there to show the player.

## Prices

Prices from OpenRouter on 2026-09-28.

| What | Price |
| --- | --- |
| Veo 3.1, 8 s clip with sound | $3.20 |
| Veo 3.1 Lite, 8 s clip | $0.40 |
| Wan 3.0, 8 s clip | $0.80 |
| Lyria 3 Pro, one song | $0.08 |
| Lyria 3 Clip, one 30 s clip | $0.04 |
| Read-aloud | about 1.5 cents per 1,000 characters |

## Good to know

- **Every message is a new paid clip or song.** Even "thanks" orders one.
- **Stop does not cancel a clip that is already ordered.** OpenRouter finishes it and bills it. You can find it at [openrouter.ai/activity](https://openrouter.ai/activity).
- **Describe the whole scene, or keep refining in the same chat.** Each new message is added to your earlier ones, so "make the banana blue" still knows what the banana is. A new chat starts from nothing.
