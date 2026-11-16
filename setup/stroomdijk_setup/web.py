"""De instelpagina van de setup (poort 8091)."""
from __future__ import annotations

import os

from aiohttp import web

STATIC = os.path.join(os.path.dirname(__file__), "static")


def maak_app(regelaar) -> web.Application:
    app = web.Application()

    async def index(request):
        return web.FileResponse(os.path.join(STATIC, "index.html"), headers={"Cache-Control": "no-cache"})

    async def status(request):
        return web.json_response(regelaar.status())

    async def verbind(request):
        body = await request.json()
        try:
            await regelaar.verbind((body.get("ssid") or "").strip(), body.get("wachtwoord") or "")
        except ValueError as e:
            return web.json_response({"fout": str(e)}, status=409)
        return web.json_response({"ok": True, "gekozen": regelaar.gekozen}, status=202)

    async def stop(request):
        await regelaar.stop()
        return web.json_response({"ok": True})

    app.router.add_get("/", index)
    app.router.add_get("/api/status", status)
    app.router.add_post("/api/verbind", verbind)
    app.router.add_post("/api/stop", stop)
    return app
