"""
title: omn1 Image
description: Make pictures from a text prompt with every OpenRouter image model.
version: 1.0.0
"""

# WHAT IT DOES
#   Adds every OpenRouter image model to the model picker ("Meta Muse Image (image)",
#   "OpenAI GPT Image 1 (image)", "Qwen Image 3 (image)", ...). The list comes from OpenRouter and
#   refreshes hourly, so new models appear by themselves. Pick one, describe the picture, send.
#   The picture is saved in Open WebUI and shown in the chat. Follow-ups in the same chat
#   ("now at night") are added to the earlier description.
#
# COST
#   Roughly $0.01 to $0.20 per picture depending on the model; the "done" line shows the real price.
#   Every message in these chats is a new paid picture. Prices: https://openrouter.ai/models?output_modalities=image
#
# SETTINGS PER MODEL
#   Models allow different shapes, qualities and resolutions. Your preferred values are sent only to
#   models that offer them; the others use their own defaults, so no order is refused for a setting.
#
# INSTALL
#   Admin Panel > Functions > New Function (+), paste this whole file, Save, then switch it on.
#   Admins: it uses the OpenRouter key already saved under Admin Panel > Settings > Connections.
#   Everyone else pays with their own key: Chat Controls (sliders icon, top right of a chat)
#   > Valves > Functions > omn1 Image > API Key.

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
    403: "OpenRouter's safety filter blocked this prompt. Try wording it differently.",
    429: "OpenRouter is rate-limiting you. Wait a minute and try again.",
}
CATALOG_SECONDS = 3600  # how long the model list is kept before asking OpenRouter again
MAX_IMAGE_BYTES = 50 * 1024 * 1024
NO_KEY = (
    "To make pictures, add your own OpenRouter key: open Chat Controls (the sliders icon at the top right), "
    "then Valves > Functions > omn1 Image, and paste it into API Key. Get a key at https://openrouter.ai/keys."
)


async def call(session, method, url, **kwargs):
    """One request to OpenRouter. Returns the body bytes, or raises an error in plain words."""
    async with session.request(method, url, **kwargs) as r:
        body = bytearray()
        async for chunk in r.content.iter_chunked(1 << 20):
            body += chunk
            if len(body) > MAX_IMAGE_BYTES:
                raise Exception(f"The picture is bigger than {MAX_IMAGE_BYTES >> 20} MB, so I did not download it.")
        if r.status < 400:
            return bytes(body)
        try:
            detail = json.loads(body)["error"]["message"]
        except Exception:
            detail = body.decode(errors="replace")
        raise Exception(PLAIN_ERRORS.get(r.status) or f"OpenRouter refused the request ({r.status}): {str(detail)[:300]}")


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


def fit(spec, v):
    """Only the preferred settings this model offers; everything else is left to the model."""
    params = spec.get("supported_parameters") or {}
    chosen = {}
    for name, want in (("aspect_ratio", v.ASPECT_RATIO), ("quality", v.QUALITY), ("resolution", v.RESOLUTION)):
        values = (params.get(name) or {}).get("values") or []
        if want and want in values:
            chosen[name] = want
    return chosen


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
            description="Empty = every OpenRouter image model, updated hourly. "
            "Or only some: comma-separated 'openrouter-id=Name in picker'.",
        )
        ASPECT_RATIO: str = Field("1:1", description="Preferred shape, e.g. 1:1, 16:9, 9:16. Sent only to models that offer it.")
        QUALITY: str = Field("", description="Preferred quality (low, medium, high). Empty = each model's default.")
        RESOLUTION: str = Field("", description="Preferred resolution (1K, 2K, 4K). Empty = each model's default.")
        TIMEOUT_SECONDS: int = Field(300, ge=30, description="Give up waiting for a picture after this many seconds")
        BASE_URL: str = Field("https://openrouter.ai/api/v1", description="OpenRouter address")
        API_KEY: str = Field(
            "",
            description="Used by admins only. Leave empty to use the key from Admin Panel > Settings > Connections",
            json_schema_extra={"input": {"type": "password"}},
        )

    class UserValves(BaseModel):
        API_KEY: str = Field(
            "",
            description="Your own OpenRouter key (https://openrouter.ai/keys). Your pictures are billed to it.",
            json_schema_extra={"input": {"type": "password"}},
        )

    def __init__(self):
        self.valves = self.Valves()
        self._catalog, self._catalog_at = {}, 0.0

    async def catalog(self):
        """OpenRouter's image models and the settings each accepts, refreshed hourly."""
        if not self._catalog or time.monotonic() - self._catalog_at > CATALOG_SECONDS:
            try:
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as s:
                    data = json.loads(await call(s, "GET", f"{self.valves.BASE_URL.rstrip('/')}/images/models"))["data"]
                self._catalog = {m["id"]: m for m in data}
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
        return [{"id": mid, "name": f"{names[mid]} (image)"} for mid in sorted(catalog, key=names.get)]

    async def api_key(self, base, user):
        """The user's own key first. The admin's keys only ever pay for the admin's own pictures."""
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
        if __task__:  # chat-title and tag requests can land here: never order a paid picture for them
            return ""
        # "Continue" must never order another paid picture. Open WebUI flags it with assistant_message_id;
        # a failed/stopped reply has no text, so the chat may still end with the user's message.
        if (__metadata__ or {}).get("assistant_message_id") or (body.get("messages") or [{}])[-1].get("role") != "user":
            return "\n\nTo make another picture, send a new message."

        async def status(text, done=False):
            if __event_emitter__:
                await __event_emitter__({"type": "status", "data": {"description": text, "done": done}})

        v = self.valves
        model = body["model"].split(".", 1)[1]
        name = next((p["name"].split(" (")[0] for p in await self.pipes() if p["id"] == model), model)
        base = v.BASE_URL.rstrip("/")
        started = time.monotonic()
        try:
            key = await self.api_key(base, __user__)
            if not key:
                return NO_KEY
            order = {"model": model, "prompt": chat_prompt(body["messages"]), "n": 1,
                     **fit((await self.catalog()).get(model, {}), v)}
            await status(f"{name} is drawing your picture...")
            # One attempt only: a retried order could be billed twice
            async with asyncio.timeout(v.TIMEOUT_SECONDS), aiohttp.ClientSession(
                headers={"Authorization": f"Bearer {key}"}, timeout=aiohttp.ClientTimeout(total=v.TIMEOUT_SECONDS)
            ) as s:
                result = json.loads(await call(s, "POST", f"{base}/images", json=order))
                item = (result.get("data") or [{}])[0]
                if item.get("b64_json"):
                    picture = base64.b64decode(item["b64_json"])
                elif item.get("url"):
                    picture = await call(s, "GET", item["url"])
                else:
                    raise Exception(f"{name} sent no picture back.")
        except TimeoutError:
            await status(f"{name}: failed", done=True)
            raise Exception(f"No picture after {v.TIMEOUT_SECONDS} seconds, so I stopped waiting. OpenRouter may still bill it.") from None
        except Exception:
            await status(f"{name}: failed", done=True)
            raise

        media_type = item.get("media_type") or "image/png"
        if not media_type.startswith("image/"):
            media_type = f"image/{media_type}"
        meta = __metadata__ or {}
        user = await Users.get_user_by_id(__user__["id"])
        _, f = await upload_image(__request__, picture, media_type, {"chat_id": meta.get("chat_id"), "message_id": meta.get("message_id")}, user)

        cost = (result.get("usage") or {}).get("cost")
        await status(f"{name}: done in {int(time.monotonic() - started)} s" + (f", cost ${cost:.2f}" if isinstance(cost, (int, float)) else ""), done=True)
        return f"Here is your picture.\n\n![{name}]({f['url']})\n"
