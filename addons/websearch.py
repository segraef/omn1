"""
title: omn1 Web Search
description: A web search switch in the chat input. When it is on, OpenRouter searches the web for your message and the model answers with sources.
version: 1.0.0
"""

# WHAT IT DOES
#   Adds a globe switch to the chat input. Switch it on and each message asks OpenRouter to search
#   the web first (OpenRouter's "web" plugin), for any OpenRouter model. Local Ollama models are left alone.
#
# COST
#   About $0.004 per result, so about $0.02 per message with the default 5 results, plus the extra
#   page text the model reads. Off by default, so everyday chats cost nothing extra.
#
# INSTALL
#   Admin Panel > Functions > New Function (+), paste this whole file, Save, switch it on,
#   then open its "..." menu and choose Global so the switch appears for every model.

from pydantic import BaseModel, Field

GLOBE = (
    "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmls"
    "bD0ibm9uZSIgc3Ryb2tlPSIjOWNhM2FmIiBzdHJva2Utd2lkdGg9IjEuOCIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIj48Y2lyY2xlIGN4PSIxMiIg"
    "Y3k9IjEyIiByPSI5Ii8+PHBhdGggZD0iTTMgMTJoMThNMTIgM2MyLjUgMi44IDIuNSAxNS4yIDAgMThNMTIgM2MtMi41IDIuOC0yLjUgMTUuMiAw"
    "IDE4Ii8+PC9zdmc+"
)


class Filter:
    class Valves(BaseModel):
        MAX_RESULTS: int = Field(5, ge=1, le=10, description="Web results per message (each costs about $0.004)")

    def __init__(self):
        self.valves = self.Valves()
        self.toggle = True  # shows up as a switch in the chat input; off until the user turns it on
        self.icon = GLOBE

    async def inlet(self, body: dict, __model__: dict | None = None) -> dict:
        if (__model__ or {}).get("owned_by") == "ollama":  # the web plugin is an OpenRouter feature
            return body
        plugins = [p for p in body.get("plugins") or [] if p.get("id") != "web"]
        plugins.append({"id": "web", "max_results": self.valves.MAX_RESULTS})
        body["plugins"] = plugins
        return body
