"""Give every model in the omn1 picker its maker's logo (Anthropic, OpenAI, Google, ...).

Run it inside the running app; rerun whenever new models show up:
    docker compose exec -T openwebui python3 - < scripts/icons.py

It covers the OpenRouter models, the image/video/music add-on models and local Ollama models.
Logos come from LobeHub's open icon set (MIT), are turned into small PNG tiles and stored inside
omn1, so the browser never fetches them from outside. Models you already edited keep their settings; only the picture changes.
Chat and local models stay visible to everyone; add-on models keep Open WebUI's default (admins only).
"""

import asyncio
import base64
import io
import json
import os
import urllib.request

# Open WebUI's code needs its login secret loaded, as the running app does
if not os.environ.get("WEBUI_SECRET_KEY") and os.environ.get("WEBUI_SECRET_KEY_FILE"):
    os.environ["WEBUI_SECRET_KEY"] = open(os.environ["WEBUI_SECRET_KEY_FILE"]).read().strip()

from PIL import Image, ImageDraw

from open_webui.models.config import Config
from open_webui.models.functions import Functions
from open_webui.models.models import ModelForm, Models
from open_webui.models.users import Users
from open_webui.utils.plugin import load_function_module_by_id

ICONS = "https://cdn.jsdelivr.net/npm/@lobehub/icons-static-png@1.97.1/light/"  # PNG: Open WebUI rejects SVG pictures
PUBLIC = [{"principal_type": "user", "principal_id": "*", "permission": "read"}]
# model maker (the part before "/") -> LobeHub icon name, where they differ
MAKERS = {
    "anthropic": "claude", "google": "gemini", "x-ai": "grok", "xai": "grok", "meta-llama": "meta",
    "alibaba": "qwen", "mistralai": "mistral", "amazon": "nova", "moonshotai": "kimi", "z-ai": "zhipu",
    "thudm": "zhipu", "baidu": "wenxin", "tencent": "hunyuan", "bytedance": "doubao", "bytedance-seed": "doubao",
    "ibm-granite": "ibm", "black-forest-labs": "flux", "kwaivgi": "kling", "stability-ai": "stability",
    "xiaomi": "xiaomimimo", "nousresearch": "nousresearch", "arcee-ai": "arcee", "inclusionai": "ling",
}
# local model names -> icon, by the family word in the name
FAMILIES = [("qwen", "qwen"), ("llama", "meta"), ("gemma", "gemma"), ("mistral", "mistral"), ("mixtral", "mistral"),
            ("deepseek", "deepseek"), ("phi", "microsoft"), ("granite", "ibm"), ("command", "cohere")]
_cache = {}


def fetch(url, timeout=20):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.read()


def icon(name):
    """LobeHub logo on a white rounded tile (readable in light and dark mode) as a PNG data: URL, or None."""
    if name in _cache:
        return _cache[name]
    logo = None
    for file in (f"{name}-color.png", f"{name}.png"):
        try:
            logo = Image.open(io.BytesIO(fetch(ICONS + file))).convert("RGBA")
            break
        except Exception:
            continue
    url = None
    if logo:
        size, pad = 96, 18
        tile = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        ImageDraw.Draw(tile).rounded_rectangle((0, 0, size - 1, size - 1), radius=22, fill=(255, 255, 255, 255))
        logo.thumbnail((size - 2 * pad, size - 2 * pad))
        tile.alpha_composite(logo, ((size - logo.width) // 2, (size - logo.height) // 2))
        out = io.BytesIO(); tile.save(out, "PNG", optimize=True)
        url = "data:image/png;base64," + base64.b64encode(out.getvalue()).decode()
    _cache[name] = url
    return url


def maker_icon(model_id):
    maker = model_id.lstrip("~").split("/", 1)[0].lower()
    return icon(MAKERS.get(maker, maker))


def local_icon(name):
    family = name.split("/")[-1].lower()
    return next((icon(i) for word, i in FAMILIES if word in family), None) or icon("ollama")


async def all_models():
    """(id, name, icon, public) for every model the picker shows."""
    found = []
    urls = await Config.get("openai.api_base_urls") or []
    for base in urls:  # OpenRouter chat models (the list itself is public)
        try:
            for m in json.loads(fetch(base.rstrip("/") + "/models"))["data"]:
                found.append((m["id"], m.get("name") or m["id"], maker_icon(m["id"]), True))
        except Exception as e:
            print(f"skipped {base}: {e}")
    for f in await Functions.get_functions_by_type("pipe", active_only=True):  # add-on models
        try:
            loaded = await load_function_module_by_id(f.id)
            module = loaded[0] if isinstance(loaded, tuple) else loaded
            valves = await Functions.get_function_valves_by_id(f.id) or {}
            if hasattr(module, "Valves"):
                module.valves = module.Valves(**valves)
            pipes = module.pipes() if callable(module.pipes) else module.pipes
            if asyncio.iscoroutine(pipes):
                pipes = await pipes
            for p in pipes:
                found.append((f"{f.id}.{p['id']}", p["name"], maker_icon(p["id"]), False))
        except Exception as e:
            print(f"skipped add-on {f.id}: {e}")
    if await Config.get("ollama.enable"):  # local models
        for base in await Config.get("ollama.base_urls") or []:
            try:
                for m in json.loads(fetch(base.rstrip("/") + "/api/tags", timeout=5))["models"]:
                    found.append((m["name"], m["name"], local_icon(m["name"]), True))
            except Exception as e:
                print(f"skipped Ollama at {base}: {e}")
    return found


async def main():
    admin = await Users.get_super_admin_user() or await Users.get_first_user()
    added = updated = no_icon = 0
    for model_id, name, logo, public in await all_models():
        if not logo:
            no_icon += 1
            continue
        existing = await Models.get_model_by_id(model_id)
        if existing:  # keep the user's name, settings and sharing; only swap the picture
            if (existing.meta.model_dump() if hasattr(existing.meta, "model_dump") else dict(existing.meta or {})).get("profile_image_url") == logo:
                continue
            meta = existing.meta.model_dump() if hasattr(existing.meta, "model_dump") else dict(existing.meta or {})
            params = existing.params.model_dump() if hasattr(existing.params, "model_dump") else dict(existing.params or {})
            meta["profile_image_url"] = logo
            await Models.update_model_by_id(model_id, ModelForm(id=model_id, base_model_id=existing.base_model_id, name=existing.name,
                                                                meta=meta, params=params, is_active=existing.is_active))
            updated += 1
        else:
            await Models.insert_new_model(ModelForm(id=model_id, name=name, meta={"profile_image_url": logo}, params={},
                                                    access_grants=PUBLIC if public else []), admin.id)
            added += 1
    print(f"logos set: {added} new, {updated} updated, {no_icon} without a known logo (kept the default)")


asyncio.run(main())
