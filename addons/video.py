"""
title: omn1 Video
description: Make short videos from a text prompt with every OpenRouter video model.
version: 1.2.0
"""

# WHAT IT DOES
#   Adds every OpenRouter video model that works from a text prompt to the model picker
#   ("Google Veo 3.1 (video)", "Kling Video v3.0 Pro (video)", "OpenAI Sora 2 Pro (video)", ...). The list comes
#   from OpenRouter and refreshes hourly, so new models appear by themselves. Models that need an
#   input video or photo (edit, upscale, avatar) are left out. Pick one, describe the scene, send. The add-on orders the clip from OpenRouter, checks
#   back every few seconds (a clip takes about 1 to 3 minutes), saves the finished MP4 in
#   Open WebUI and shows a video player in the chat. Follow-ups in the same chat ("make the
#   banana blue") are added to the earlier description, so each clip sees the whole story.
#
# COST (OpenRouter, September 2026, 8-second 720p clip): from about $0.40 (Veo 3.1 Lite, Wan 3.0)
#   to $3.20 (Veo 3.1) and $2.40 (Sora 2 Pro). The "done" line shows the real price of each clip.
#   Every message in these chats is a new paid clip. Prices: https://openrouter.ai/api/v1/videos/models
#
# SETTINGS PER MODEL
#   Each model allows different lengths, resolutions and shapes. The add-on uses your preferred
#   values when a model offers them, otherwise the closest length, the lowest resolution and the
#   model's first shape, so no order is refused for an unsupported setting.
#
# INSTALL
#   Admin Panel > Functions > New Function (+), paste this whole file, Save, then switch it on.
#   Admins: it uses the OpenRouter key already saved under Admin Panel > Settings > Connections.
#   Everyone else pays with their own key: Chat Controls (sliders icon, top right of a chat)
#   > Valves > Functions > omn1 Video > API Key. The gear icon next to the function holds the settings below.

import asyncio
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
    403: "OpenRouter's safety filter blocked this prompt. Try wording it differently.",
    429: "OpenRouter is rate-limiting you. Wait a minute and try again.",
}
DOWNLOAD_SECONDS = 300
CATALOG_SECONDS = 3600  # how long the model list is kept before asking OpenRouter again
RESOLUTIONS = ["480p", "720p", "768p", "1080p", "2K", "4K"]  # low to high
MAX_VIDEO_BYTES = 200 * 1024 * 1024
NO_KEY = (
    "To make videos, add your own OpenRouter key: open Chat Controls (the sliders icon at the top right), "
    "then Valves > Functions > omn1 Video, and paste it into API Key. Get a key at https://openrouter.ai/keys."
)


class Busy(Exception):
    """OpenRouter is busy, rate-limiting or briefly broken: worth asking again."""


async def call(session, method, url, limit=None, **kwargs):
    """One request to OpenRouter. Returns the body bytes, or raises an error in plain words."""
    async with session.request(method, url, **kwargs) as r:
        body = bytearray()
        async for chunk in r.content.iter_chunked(1 << 20):
            body += chunk
            if limit and len(body) > limit:
                raise Exception(f"The video is bigger than {limit >> 20} MB, so I did not download it.")
        if r.status < 400:
            return bytes(body)
        try:
            detail = json.loads(body)["error"]["message"]
        except Exception:
            detail = body.decode(errors="replace")
        error = Busy if r.status in (408, 409, 429) or r.status >= 500 else Exception
        raise error(PLAIN_ERRORS.get(r.status) or f"OpenRouter refused the request ({r.status}): {str(detail)[:300]}")


async def get_patiently(session, url, wait, **kwargs):
    """GET that shrugs off hiccups and asks again after `wait` seconds. The caller sets the deadline."""
    while True:
        try:
            return await call(session, "GET", url, **kwargs)
        except (Busy, aiohttp.ClientError):
            await asyncio.sleep(wait)


def fit(spec, v):
    """The valve settings, adjusted to what this model offers (None = let the model decide)."""
    durations = spec.get("supported_durations") or []
    resolutions = spec.get("supported_resolutions") or []
    ratios = spec.get("supported_aspect_ratios") or []
    duration = min(durations, key=lambda d: (abs(d - v.DURATION), d)) if durations else None
    rank = {r: i for i, r in enumerate(RESOLUTIONS)}
    resolution = v.RESOLUTION if v.RESOLUTION in resolutions else min(resolutions, key=lambda r: rank.get(r, 99)) if resolutions else None
    ratio = v.ASPECT_RATIO if v.ASPECT_RATIO in ratios else (ratios[0] if ratios else None)
    return duration, resolution, ratio


def chat_prompt(messages):
    """Every user message in the chat, oldest first, so follow-ups keep the original description."""
    texts = []
    for m in messages:
        if m.get("role") != "user":
            continue
        content = m.get("content") or ""
        if isinstance(content, list):  # message with attachments: keep the text parts
            content = " ".join(p.get("text", "") for p in content if p.get("type") == "text")
        if content.strip():
            texts.append(content.strip())
    return "\n".join(texts)


def picker_name(name):
    """'Google: Veo 3.1' -> 'Google Veo 3.1', but 'Qwen: Qwen Image 3' -> 'Qwen Image 3'."""
    maker, _, model = name.partition(": ")
    if not model:
        return name
    return model if model.lower().startswith(maker.lower()) else f"{maker} {model}"


class Pipe:
    class Valves(BaseModel):
        MODELS: str = Field(
            "",
            description="Empty = every OpenRouter video model that works from text, updated hourly. "
            "Or only some: comma-separated 'openrouter-id=Name in picker'.",
        )
        DURATION: int = Field(8, ge=1, description="Preferred seconds per clip. Models without it use their closest length.")
        RESOLUTION: str = Field("720p", description="Preferred resolution. Models without it use their lowest one.")
        ASPECT_RATIO: str = Field("16:9", description="Preferred shape: 16:9 landscape, 9:16 portrait. Models without it use their first one.")
        POLL_SECONDS: int = Field(10, ge=5, description="How often to ask whether the clip is ready (at least 5)")
        TIMEOUT_SECONDS: int = Field(600, ge=60, description="Give up waiting for the clip after this many seconds (at least 60)")
        BASE_URL: str = Field("https://openrouter.ai/api/v1", description="OpenRouter address")
        API_KEY: str = Field(
            "",
            description="Used by admins only. Leave empty to use the key from Admin Panel > Settings > Connections",
            json_schema_extra={"input": {"type": "password"}},
        )

    class UserValves(BaseModel):
        API_KEY: str = Field(
            "",
            description="Your own OpenRouter key (https://openrouter.ai/keys). Your clips are billed to it.",
            json_schema_extra={"input": {"type": "password"}},
        )

    def __init__(self):
        self.valves = self.Valves()
        self._catalog, self._catalog_at = {}, 0.0

    async def catalog(self):
        """OpenRouter's text-to-video models and what each supports, refreshed hourly."""
        if not self._catalog or time.monotonic() - self._catalog_at > CATALOG_SECONDS:
            try:
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as s:
                    data = json.loads(await call(s, "GET", f"{self.valves.BASE_URL.rstrip('/')}/videos/models"))["data"]
                # models without lengths need an input video or photo; this add-on only sends text
                self._catalog = {m["id"]: m for m in data if m.get("supported_durations")}
                self._catalog_at = time.monotonic()
            except Exception:
                pass  # keep the last good list (empty if OpenRouter was never reached)
        return self._catalog

    async def pipes(self):
        if self.valves.MODELS.strip():
            models = []
            for item in self.valves.MODELS.split(","):
                model_id, _, name = item.partition("=")
                if model_id.strip():
                    models.append({"id": model_id.strip(), "name": (name or model_id).strip()})
            return models
        catalog = await self.catalog()
        names = {mid: picker_name(m.get("name", mid)) for mid, m in catalog.items()}
        return [{"id": mid, "name": f"{names[mid]} (video)"} for mid in sorted(catalog, key=names.get)]

    async def api_key(self, base, user):
        """The user's own key first. The admin's keys only ever pay for the admin's own clips."""
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
        if __task__:  # chat-title and tag requests can land here: never order a paid clip for them
            return ""
        # "Continue" must never order another paid clip. Open WebUI flags it with assistant_message_id;
        # a failed/stopped reply has no text, so the chat may still end with the user's message.
        # The note is glued onto the old reply, so the blank line keeps the player's tag on its own.
        if (__metadata__ or {}).get("assistant_message_id") or (body.get("messages") or [{}])[-1].get("role") != "user":
            return "\n\nTo make another clip, send a new message."

        async def status(text, done=False):
            if __event_emitter__:
                await __event_emitter__({"type": "status", "data": {"description": text, "done": done}})

        v = self.valves
        model = body["model"].split(".", 1)[1]
        name = next((p["name"].split(" (")[0] for p in await self.pipes() if p["id"] == model), model)
        duration, resolution, ratio = fit((await self.catalog()).get(model, {}), self.valves)
        prompt = chat_prompt(body["messages"])
        base = v.BASE_URL.rstrip("/")
        started = time.monotonic()
        job_id = None

        try:
            key = await self.api_key(base, __user__)
            if not key:
                return NO_KEY
            headers = {"Authorization": f"Bearer {key}"}
            # asyncio.timeout is the one deadline; aiohttp's own 5-minute default is switched off
            async with aiohttp.ClientSession(headers=headers, timeout=aiohttp.ClientTimeout(total=None, sock_read=60)) as s:  # a hung check is retried
                try:
                    async with asyncio.timeout(v.TIMEOUT_SECONDS):
                        shown = ", ".join(str(x) for x in (duration and f"{duration} s", resolution, ratio) if x)
                        await status(f"{name}: sending your request{f' ({shown})' if shown else ''}...")
                        order = {"model": model, "prompt": prompt, "duration": duration, "resolution": resolution, "aspect_ratio": ratio}
                        order = {k: val for k, val in order.items() if val is not None}
                        job = json.loads(await call(s, "POST", f"{base}/videos", json=order))
                        job_id = job["id"]
                        while job.get("status") not in ("completed", "failed", "cancelled", "expired"):
                            await status(f"{name} is making your video: {int(time.monotonic() - started)} s so far (usually 1 to 3 min)")
                            await asyncio.sleep(v.POLL_SECONDS)
                            job = json.loads(await get_patiently(s, f"{base}/videos/{job_id}", v.POLL_SECONDS))
                except TimeoutError:
                    raise Exception(
                        f"No finished video after {v.TIMEOUT_SECONDS / 60:g} minutes, so I stopped waiting. "
                        "OpenRouter may still finish and bill it."
                    ) from None
            if job["status"] != "completed":
                raise Exception(f"{name} could not make this video: {job.get('error') or job['status']}")

            # The download gets its own 5 minutes, so a slow clip does not eat into it
            await status(f"{name}: downloading...")
            try:
                async with asyncio.timeout(DOWNLOAD_SECONDS), aiohttp.ClientSession(
                    headers=headers, timeout=aiohttp.ClientTimeout(total=DOWNLOAD_SECONDS)
                ) as s:
                    video = await get_patiently(s, f"{base}/videos/{job_id}/content", v.POLL_SECONDS, params={"index": "0"}, limit=MAX_VIDEO_BYTES)
            except TimeoutError:
                raise Exception("The video is finished, but downloading it took longer than 5 minutes.") from None
        except Exception as e:
            await status(f"{name}: failed", done=True)
            if job_id:  # the clip was ordered: say where to find it
                raise Exception(f"{str(e).rstrip('.')}. OpenRouter job: {job_id} (see https://openrouter.ai/activity)") from None
            raise

        meta = __metadata__ or {}
        user = await Users.get_user_by_id(__user__["id"])
        # ponytail: reuses Open WebUI's image saver, so a downloaded clip is named "generated-image.mp4"
        _, f = await upload_image(__request__, video, "video/mp4", {"chat_id": meta.get("chat_id"), "message_id": meta.get("message_id")}, user)

        cost = (job.get("usage") or {}).get("cost")
        await status(f"{name}: done in {int(time.monotonic() - started)} s" + (f", cost ${cost:.2f}" if isinstance(cost, (int, float)) else ""), done=True)
        # Open WebUI v0.11.4 only draws a player when the tag stands alone with the address on its own line
        return f"Here is your clip.\n\n<video>\n{f['url']}\n</video>\n\n"
