"""Richt een lege Home Assistant in voor Stroomdijk, zonder browser.

Doorloopt de onboarding-stappen van Home Assistant (eigenaar aanmaken, basisinstellingen,
afronden) en maakt een long-lived token voor de Stroomdijk-app. Wachtwoord en token
gaan naar bestanden in /geheim (op de Pi: ~/stroomdijk/geheim) en worden nooit getoond.

Draait in een wegwerpcontainer met het Home Assistant-image (daar zit aiohttp al in):
  docker run --rm --network host -v ~/stroomdijk/geheim:/geheim \
    -v ~/stroomdijk/scripts:/scripts:ro --entrypoint python3 \
    ghcr.io/home-assistant/home-assistant:stable /scripts/inrichten.py
"""
import asyncio
import os
import secrets
import sys

import aiohttp

HA = os.environ.get("HA_URL", "http://127.0.0.1:8124")
CLIENT = "http://stroomdijk.local:8090/"
GEHEIM = "/geheim"
EIGENAAR_UID = 1000  # gebruiker admin op de Pi, zodat die de bestanden zonder sudo kan lezen


def bewaar(naam, waarde):
    pad = os.path.join(GEHEIM, naam)
    fd = os.open(pad, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(waarde + "\n")
    os.chown(pad, EIGENAAR_UID, EIGENAAR_UID)


async def wacht_op_ha(s):
    for _ in range(90):
        try:
            async with s.get(f"{HA}/api/onboarding") as r:
                if r.status == 200:
                    return await r.json()
        except aiohttp.ClientError:
            pass
        await asyncio.sleep(2)
    sys.exit("Home Assistant reageert niet op " + HA)


async def main():
    async with aiohttp.ClientSession() as s:
        stappen = {x["step"]: x["done"] for x in await wacht_op_ha(s)}
        if stappen.get("user"):
            if os.path.exists(os.path.join(GEHEIM, "ha_token")):
                print("Al ingericht, token staat er al. Niets gedaan.")
                return
            sys.exit("Home Assistant heeft al een eigenaar, maar er is geen token in geheim/. Stop.")

        wachtwoord = secrets.token_urlsafe(24)
        bewaar("ha_wachtwoord", wachtwoord)  # eerst bewaren, dan pas gebruiken

        async with s.post(f"{HA}/api/onboarding/users", json={
            "client_id": CLIENT, "name": "Stroomdijk", "username": "stroomdijk",
            "password": wachtwoord, "language": "nl"}) as r:
            print("eigenaar aanmaken:", r.status)
            r.raise_for_status()
            code = (await r.json())["auth_code"]

        async with s.post(f"{HA}/auth/token", data={
            "grant_type": "authorization_code", "code": code, "client_id": CLIENT}) as r:
            print("inloggen:", r.status)
            r.raise_for_status()
            toegang = (await r.json())["access_token"]
        kop = {"Authorization": f"Bearer {toegang}"}

        for stap, body in (("core_config", {}), ("analytics", {}),
                           ("integration", {"client_id": CLIENT, "redirect_uri": CLIENT})):
            async with s.post(f"{HA}/api/onboarding/{stap}", headers=kop, json=body) as r:
                print(f"stap {stap}:", r.status)

        async with s.ws_connect(f"{HA}/api/websocket") as ws:
            await ws.receive_json()
            await ws.send_json({"type": "auth", "access_token": toegang})
            if (await ws.receive_json())["type"] != "auth_ok":
                sys.exit("WebSocket-inloggen mislukt")
            await ws.send_json({"id": 1, "type": "auth/long_lived_access_token",
                                "client_name": "stroomdijk-app", "lifespan": 3650})
            m = await ws.receive_json()
            if not m.get("success"):
                sys.exit(f"token maken mislukt: {m.get('error')}")
            bewaar("ha_token", m["result"])
        print("Klaar. Wachtwoord en token staan in geheim/.")


asyncio.run(main())
