"""Add "omn1 Auto" to the model picker: it picks the best model from YOUR pool for each message.

Uses OpenRouter's Auto Router (no extra fee): it sorts each prompt into a task type (coding, writing,
questions, ...) and sends it to the model from your pool that people use most for that task.
The answer shows up as "omn1 Auto"; which model answered is listed on openrouter.ai/activity.

Edit POOL and COST_TIER below, then run (again) inside the app:
    docker compose exec -T openwebui python3 - < scripts/auto.py
"""

import asyncio
import base64
import io
import json
import os

# Open WebUI's code needs its login secret loaded, as the running app does
if not os.environ.get("WEBUI_SECRET_KEY") and os.environ.get("WEBUI_SECRET_KEY_FILE"):
    os.environ["WEBUI_SECRET_KEY"] = open(os.environ["WEBUI_SECRET_KEY_FILE"]).read().strip()

from PIL import Image, ImageDraw
from open_webui.models.models import ModelForm, Models
from open_webui.models.users import Users

# Models omn1 Auto may choose from. Exact OpenRouter IDs, or patterns like "anthropic/*".
POOL = [
    "anthropic/claude-opus-5.5",
    "anthropic/claude-sonnet-5",
    "openai/gpt-6-sol",
    "openai/gpt-6-luna",
    "google/gemini-3.1-pro-preview",
    "google/gemini-3.5-flash",
    "deepseek/deepseek-v4-pro",
    "qwen/qwen3.7-max",
]
COST_TIER = "medium"  # low, medium or high: how much the router may spend per answer

MODEL_ID, NAME = "omn1-auto", "omn1 Auto"
PUBLIC = [{"principal_type": "user", "principal_id": "*", "permission": "read"}]


def logo():
    """The omn1 mark (four coloured arcs around a 1) on a white tile, as a PNG data: URL."""
    k, size = 4, 96  # draw 4x larger, then shrink for smooth edges
    img = Image.new("RGBA", (size * k, size * k), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, size * k - 1, size * k - 1), radius=22 * k, fill="#ffffff")
    s, ox = 64 / 68 * k, 16 * k  # the mark is drawn in a 68-unit box, placed as 64 px inside the tile
    box = [ox + (34 - 26) * s, ox + (34 - 26) * s, ox + (34 + 26) * s, ox + (34 + 26) * s]
    for start, colour in ((270, "#2563eb"), (0, "#7c3aed"), (90, "#db2777"), (180, "#0891b2")):
        d.arc(box, start, start + 90, fill=colour, width=round(7 * s))
    one = [(28, 25), (36, 20), (39, 20), (39, 48), (33, 48), (33, 28.5), (28, 31)]
    d.polygon([(ox + x * s, ox + y * s) for x, y in one], fill="#6366f1")
    out = io.BytesIO()
    img.resize((size, size), Image.LANCZOS).save(out, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(out.getvalue()).decode()


async def main():
    admin = await Users.get_super_admin_user() or await Users.get_first_user()
    plugins = [{"id": "auto-router", "allowed_models": POOL, "cost_tier": COST_TIER}]
    form = ModelForm(
        id=MODEL_ID,
        base_model_id="openrouter/auto",
        name=NAME,
        meta={"profile_image_url": logo(),
              "description": f"Picks the best of {len(POOL)} models for each message ({COST_TIER} cost)."},
        params={"custom_params": {"plugins": json.dumps(plugins)}},  # sent along with every request
        access_grants=PUBLIC,
    )
    if await Models.get_model_by_id(MODEL_ID):
        await Models.update_model_by_id(MODEL_ID, form)
        print(f"{NAME} updated: {len(POOL)} models, {COST_TIER} cost")
    else:
        await Models.insert_new_model(form, admin.id)
        print(f"{NAME} added: {len(POOL)} models, {COST_TIER} cost")


asyncio.run(main())
