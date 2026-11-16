import asyncio
import json

from stroomdijk.demo import DemoHuis
from stroomdijk.huis import Huis
from stroomdijk.web import maak_app


async def lees_event(resp):
    regels = []
    while True:
        r = (await asyncio.wait_for(resp.content.readline(), 3)).decode()
        if r == "\n" and regels:
            break
        if r.startswith("data: "):
            regels.append(r[6:])
    return json.loads("".join(regels))


async def test_demo_pagina_en_api(aiohttp_client):
    demo = DemoHuis(interval=0.05)
    await demo.start()
    c = await aiohttp_client(maak_app(demo))

    r = await c.get("/")
    assert r.status == 200 and "Stroomdijk" in await r.text()

    o = await (await c.get("/api/now")).json()
    assert o["demo"] and o["zon"]["w"] > 0 and len(o["net"]["fasen"]) == 3 and "ts" in o
    assert o["huis_w"] == o["zon"]["w"] + o["net"]["w"]

    assert (await (await c.get("/healthz")).json())["ok"]
    assert (await c.get("/static/icon.svg")).status == 200
    await demo.stop()


async def test_stroom_stuurt_meteen_en_bij_wijziging(aiohttp_client):
    demo = DemoHuis(interval=0.05)
    await demo.start()
    c = await aiohttp_client(maak_app(demo, ping=0.05))
    resp = await c.get("/api/stream")
    assert resp.headers["Content-Type"].startswith("text/event-stream")
    eerste = await lees_event(resp)
    tweede = await lees_event(resp)
    assert tweede["ts"] >= eerste["ts"]
    assert len(demo.luisteraars) == 1
    resp.close()
    await demo.stop()


async def test_echt_huis_leeg_en_daarna_live(aiohttp_client, client, nep, status, integraties):
    from test_rollen_huis import koppel
    huis = Huis(client, status, integraties)
    await huis.start()
    await huis.ververs()
    c = await aiohttp_client(maak_app(huis))
    o = await (await c.get("/api/now")).json()
    assert o["zon"] is None and o["net"] is None and o["verbonden"] and not o.get("demo")

    resp = await c.get("/api/stream")
    await lees_event(resp)
    await koppel(client, status, integraties, nep, "enphase_envoy", {"password": "goed"})
    for _ in range(5):
        o = await lees_event(resp)
        if o["zon"]:
            break
    assert o["zon"]["w"] == 1234
    resp.close()
