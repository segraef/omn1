"""
title: omn1 Music
description: Make songs from a text prompt with Google's Lyria 3 through OpenRouter.
version: 1.1.0
"""

# WHAT IT DOES
#   Adds "Lyria 3 Pro (music)" and "Lyria 3 Clip (music)" to the model picker. Describe the song
#   (style, mood, instruments, lyrics or "instrumental", length), send, and get an audio player in
#   the chat, with the lyrics underneath when the song has any. Pro makes full songs of a couple of
#   minutes; Clip always makes 30 seconds. Follow-ups in the same chat ("slower, add a piano") are
#   added to the earlier description, so each song sees the whole request.
#
# COST (OpenRouter prices, September 2026)
#   Lyria 3 Pro $0.08 per song   Lyria 3 Clip $0.04 per clip   Every message is a new paid song.
#
# INSTALL
#   Admin Panel > Functions > New Function (+), paste this whole file, Save, then switch it on.
#   Admins: it uses the OpenRouter key already saved under Admin Panel > Settings > Connections.
#   Everyone else pays with their own key: Chat Controls (sliders icon, top right of a chat)
#   > Valves > Functions > omn1 Music > API Key. The gear icon next to the function holds the settings below.

import asyncio
import base64
import json
import time

import aiohttp
from pydantic import BaseModel, Field
from open_webui.models.config import Config
from open_webui.models.users import Users
from open_webui.routers.images import upload_image

PLAIN_ERRORS = {
    401: "OpenRouter did not accept the key. Check it under Admin Panel > Settings > Connections, or in your own add-on settings.",
    402: "Your OpenRouter credit is used up. Top it up at https://openrouter.ai/settings/credits.",
    429: "OpenRouter is rate-limiting you. Wait a minute and try again.",
}
NO_KEY = (
    "To make songs, add your own OpenRouter key: open Chat Controls (the sliders icon at the top right), "
    "then Valves > Functions > omn1 Music, and paste it into API Key. Get a key at https://openrouter.ai/keys."
)


async def call(session, method, url, **kwargs):
    """One request to OpenRouter. Returns the body bytes, or raises an error in plain words."""
    async with session.request(method, url, **kwargs) as r:
        body = await r.read()
        if r.status < 400:
            return body
        try:
            detail = json.loads(body)["error"]["message"]
        except Exception:
            detail = body.decode(errors="replace")
        raise Exception(PLAIN_ERRORS.get(r.status) or f"OpenRouter refused the request ({r.status}): {str(detail)[:300]}")


OUR_REPLIES = ("Here is your picture.", "Here is your clip.", "Here is your song.", "To make another")


def chat_prompt(messages):
    """The user's messages since the chat last talked to a normal text model, oldest first.
    Follow-ups ("make it blue") keep the earlier description; earlier text chat is left out."""
    texts = []
    for m in reversed(messages):
        content = m.get("content") or ""
        if isinstance(content, list):  # message with attachments: keep the text parts
            content = " ".join(p.get("text", "") for p in content if p.get("type") == "text")
        content = content.strip()
        if m.get("role") == "assistant" and content and not content.startswith(OUR_REPLIES):
            break  # a text model answered here: what came before is a different conversation
        if m.get("role") == "user" and content:
            texts.insert(0, content)
    return "\n".join(texts)


class Pipe:
    class Valves(BaseModel):
        MODELS: str = Field(
            "google/lyria-3-pro-preview=Lyria 3 Pro (music), google/lyria-3-clip-preview=Lyria 3 Clip (music)",
            description="Comma-separated 'openrouter-id=Name in picker'",
        )
        TIMEOUT_SECONDS: int = Field(300, ge=60, description="Give up after this many seconds (at least 60)")
        BASE_URL: str = Field("https://openrouter.ai/api/v1", description="OpenRouter address")
        API_KEY: str = Field(
            "",
            description="Used by admins only. Leave empty to use the key from Admin Panel > Settings > Connections",
            json_schema_extra={"input": {"type": "password"}},
        )

    class UserValves(BaseModel):
        API_KEY: str = Field(
            "",
            description="Your own OpenRouter key (https://openrouter.ai/keys). Your songs are billed to it.",
            json_schema_extra={"input": {"type": "password"}},
        )

    def __init__(self):
        self.valves = self.Valves()

    def pipes(self):
        models = []
        for item in self.valves.MODELS.split(","):
            model_id, _, name = item.partition("=")
            if model_id.strip():
                models.append({"id": model_id.strip(), "name": (name or model_id).strip()})
        return models

    async def api_key(self, base, user):
        """The user's own key first. The admin's keys only ever pay for the admin's own songs."""
        own = getattr(user.get("valves"), "API_KEY", "")
        if own or user.get("role") != "admin":
            return own
        if self.valves.API_KEY:
            return self.valves.API_KEY
        urls = await Config.get("openai.api_base_urls") or []
        keys = await Config.get("openai.api_keys") or []
        key = next((k for u, k in zip(urls, keys) if u.rstrip("/") == base and k), None)
        if not key:
            raise Exception("No OpenRouter key found. Paste it under Admin Panel > Settings > Connections.")
        return key

    async def pipe(self, body, __user__, __request__, __metadata__=None, __event_emitter__=None, __task__=None):
        if __task__:  # chat-title and tag requests can land here: never order a paid song for them
            return ""
        # "Continue" must never order another paid song. Open WebUI flags it with assistant_message_id;
        # a failed/stopped reply has no text, so the chat may still end with the user's message.
        # The note is glued onto the old reply, so the blank line keeps the player's tag on its own.
        if (__metadata__ or {}).get("assistant_message_id") or (body.get("messages") or [{}])[-1].get("role") != "user":
            return "\n\nTo make another song, send a new message."

        async def status(text, done=False):
            if __event_emitter__:
                await __event_emitter__({"type": "status", "data": {"description": text, "done": done}})

        v = self.valves
        model = body["model"].split(".", 1)[1]
        name = next((p["name"].split(" (")[0] for p in self.pipes() if p["id"] == model), model)
        prompt = chat_prompt(body["messages"])
        base = v.BASE_URL.rstrip("/")
        started = time.monotonic()

        try:
            key = await self.api_key(base, __user__)
            if not key:
                return NO_KEY
            headers = {"Authorization": f"Bearer {key}"}
            await status(f"{name} is composing your song (usually 30 s to 2 min)...")
            # OpenRouter only returns sound when streaming. Lyria takes no voice, only a file format.
            order = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "modalities": ["text", "audio"],
                "audio": {"format": "mp3"},
                "stream": True,
            }
            # asyncio.timeout is the one deadline; aiohttp's own 5-minute default is switched off
            async with asyncio.timeout(v.TIMEOUT_SECONDS), aiohttp.ClientSession(
                headers=headers, timeout=aiohttp.ClientTimeout(total=None)
            ) as s:
                stream = await call(s, "POST", f"{base}/chat/completions", json=order)

            # The reply is a stream of "data: {json}" lines. The sound arrives as base64 slices that
            # only decode correctly once joined, so collect them all first.
            sound, lyrics, cost = [], [], None
            for line in stream.decode().split("\n"):  # not splitlines(): that also splits inside the JSON text
                data = line[5:].strip() if line.startswith("data:") else ""
                if not data or data == "[DONE]":
                    continue
                chunk = json.loads(data)
                if chunk.get("error"):
                    raise Exception(f"{name} could not make this song: {chunk['error'].get('message') or chunk['error']}")
                delta = (chunk.get("choices") or [{}])[0].get("delta") or {}
                audio = delta.get("audio") or {}
                sound.append(audio.get("data") or "")
                lyrics.append(audio.get("transcript") or delta.get("content") or "")
                cost = (chunk.get("usage") or {}).get("cost", cost)
            song = base64.b64decode("".join(sound))
            if not song:
                raise Exception(f"{name} sent back no sound. Try again or reword the prompt.")
            # mp3 is requested; a WAV is fine too. Anything else would only show a broken player.
            if song[:3] == b"ID3" or (len(song) > 1 and song[0] == 0xFF and song[1] & 0xE0 == 0xE0):
                mime = "audio/mpeg"
            elif song[:4] == b"RIFF":
                mime = "audio/x-wav"  # not "audio/wav": Python 3.11 finds no file ending for that one
            else:
                raise Exception(f"{name} sent sound in a format the browser cannot play. Try again.")
        except TimeoutError:
            await status(f"{name}: stopped waiting", done=True)
            raise Exception(f"No song after {v.TIMEOUT_SECONDS / 60:g} minutes, so I stopped waiting. Try again.") from None
        except Exception:
            await status(f"{name}: failed", done=True)
            raise

        meta = __metadata__ or {}
        user = await Users.get_user_by_id(__user__["id"])
        # ponytail: reuses Open WebUI's image saver, so a downloaded song is named "generated-image.mp3"
        _, f = await upload_image(__request__, song, mime, {"chat_id": meta.get("chat_id"), "message_id": meta.get("message_id")}, user)

        await status(f"{name}: done in {int(time.monotonic() - started)} s" + (f", cost ${cost:.2f}" if isinstance(cost, (int, float)) else ""), done=True)
        # Open WebUI v0.11.4 only draws a player when the tag stands alone with the address on its own line
        return f"Here is your song.\n\n<audio>\n{f['url']}\n</audio>\n\n" + "".join(lyrics).strip()
