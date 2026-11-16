"""De webserver van de Stroomdijk-app: pagina, momentopname, live stroom en gezondheid."""
from __future__ import annotations

import asyncio
import json
import os
import time

from aiohttp import web

STATIC = os.path.join(os.path.dirname(__file__), "static")
PING = 15.0


def _momentopname(huis) -> dict:
    o = dict(huis.overzicht())
    o["ts"] = time.time()
    return o


def maak_app(huis, ping: float = PING) -> web.Application:
    app = web.Application()
    app["huis"] = huis

    async def index(request):
        return web.FileResponse(os.path.join(STATIC, "index.html"),
                                headers={"Cache-Control": "no-cache"})

    async def nu(request):
        return web.json_response(_momentopname(huis))

    async def gezond(request):
        o = huis.overzicht()
        return web.json_response({"ok": True, "verbonden": o.get("verbonden"), "fout": o.get("fout")})

    async def stroom(request):
        resp = web.StreamResponse(headers={"Content-Type": "text/event-stream",
                                           "Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
        await resp.prepare(request)
        wacht: asyncio.Queue = asyncio.Queue(maxsize=1)

        def melding():
            if not wacht.full():
                wacht.put_nowait(None)

        async def stuur():
            data = json.dumps(_momentopname(huis), separators=(",", ":"))
            await resp.write(f"data: {data}\n\n".encode())

        huis.luisteraars.append(melding)
        try:
            await stuur()
            while True:
                try:
                    await asyncio.wait_for(wacht.get(), ping)
                    await stuur()
                except asyncio.TimeoutError:
                    await resp.write(b": ping\n\n")
        except (ConnectionResetError, ConnectionError):
            pass
        finally:
            huis.luisteraars.remove(melding)
        return resp

    app.router.add_get("/", index)
    app.router.add_get("/api/now", nu)
    app.router.add_get("/api/stream", stroom)
    app.router.add_get("/healthz", gezond)
    app.router.add_static("/static", STATIC)
    return app
