"""Verwijdert koppelingen uit de Stroomdijk-Home Assistant die daar niet horen.

Een nieuwe Home Assistant koppelt sommige gevonden apparaten vanzelf zolang hij nog
niet is ingericht (bijvoorbeeld Sonos en de Bluetooth-chip). Dit script haalt
koppelingen van de opgegeven integraties weer weg. Alleen in de Stroomdijk-HA (8124).

  docker run --rm --network host -v ~/stroomdijk/geheim:/geheim:ro \
    -v ~/stroomdijk/scripts:/scripts:ro --entrypoint python3 \
    ghcr.io/home-assistant/home-assistant:stable /scripts/opruimen.py sonos bluetooth
"""
import asyncio
import os
import sys

import aiohttp

HA = os.environ.get("HA_URL", "http://127.0.0.1:8124")


async def main(domeinen):
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
                    return m

        for e in (await vraag(type="config_entries/get"))["result"]:
            if e["domain"] in domeinen:
                async with s.delete(f"{HA}/api/config/config_entries/entry/{e['entry_id']}",
                                    headers={"Authorization": f"Bearer {token}"}) as r:
                    print(f"verwijderd: {e['domain']} ({e.get('title')}): {r.status}")


asyncio.run(main(set(sys.argv[1:])))
