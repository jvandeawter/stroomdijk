"""Laat de sensoren van een integratie in de Stroomdijk-HA zien, om rolregels te controleren.

Alleen lezen. Toont per entiteit: entity_id, translation_key, device_class, eenheid, waarde.
  docker run --rm --network host -v ~/stroomdijk/geheim:/geheim:ro \
    -v ~/stroomdijk/scripts:/scripts:ro --entrypoint python3 \
    ghcr.io/home-assistant/home-assistant:stable /scripts/entiteiten.py enphase_envoy
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

        async def vraag(soort):
            nonlocal n
            n += 1
            await ws.send_json({"id": n, "type": soort})
            while True:
                m = await ws.receive_json()
                if m.get("id") == n:
                    return m["result"]

        entries = {e["entry_id"]: e["domain"] for e in await vraag("config_entries/get")}
        apparaten = {d["id"]: d.get("name") for d in await vraag("config/device_registry/list")}
        states = {x["entity_id"]: x for x in await vraag("get_states")}
        for e in await vraag("config/entity_registry/list"):
            if entries.get(e.get("config_entry_id")) not in domeinen:
                continue
            st = states.get(e["entity_id"]) or {}
            a = st.get("attributes", {})
            print(f"{e['entity_id']:<55} tk={str(e.get('translation_key')):<32} "
                  f"dc={str(a.get('device_class')):<8} {st.get('state', '-'):>10} {a.get('unit_of_measurement', '')}"
                  f"  [{apparaten.get(e.get('device_id'), '')}]{'  UIT' if e.get('disabled_by') else ''}")


asyncio.run(main(set(sys.argv[1:])))
