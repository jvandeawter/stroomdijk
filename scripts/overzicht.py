"""Laat zien wat de Stroomdijk-Home Assistant kent: koppelingen, gevonden apparaten, sensoren.

Alleen lezen. Draait net als inrichten.py in een wegwerpcontainer:
  docker run --rm --network host -v ~/stroomdijk/geheim:/geheim:ro \
    -v ~/stroomdijk/scripts:/scripts:ro --entrypoint python3 \
    ghcr.io/home-assistant/home-assistant:stable /scripts/overzicht.py
"""
import asyncio
import os

import aiohttp

HA = os.environ.get("HA_URL", "http://127.0.0.1:8124")


async def main():
    token = open("/geheim/ha_token").read().strip()
    async with aiohttp.ClientSession() as s, s.ws_connect(f"{HA}/api/websocket") as ws:
        await ws.receive_json()
        await ws.send_json({"type": "auth", "access_token": token})
        assert (await ws.receive_json())["type"] == "auth_ok", "inloggen mislukt"
        n = 0

        async def vraag(**msg):
            nonlocal n
            n += 1
            await ws.send_json({"id": n, **msg})
            while True:
                m = await ws.receive_json()
                if m.get("id") == n:
                    return m.get("result") if m.get("success") else {"fout": m.get("error")}

        entries = await vraag(type="config_entries/get")
        print("KOPPELINGEN:")
        for e in entries:
            print(f"  {e['domain']:<20} {e.get('state'):<12} {e.get('source'):<10} {e.get('title')}")

        flows = await vraag(type="config_entries/flow/progress")
        print("GEVONDEN, NOG NIET GEKOPPELD:")
        if isinstance(flows, dict):
            print("  ", flows)
        for f in flows or []:
            ctx = f.get("context", {})
            print(f"  {f['handler']:<20} via {ctx.get('source'):<10} {ctx.get('title_placeholders', {})}")

        states = await vraag(type="get_states")
        energie = [x for x in states if x["attributes"].get("device_class") in ("power", "energy")]
        print(f"SENSOREN: {len(states)} in totaal, {len(energie)} voor vermogen of energie")


asyncio.run(main())
