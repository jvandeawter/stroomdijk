"""Een lege Home Assistant inrichten voor Stroomdijk, zonder browser.

Doorloopt de onboarding (eigenaar aanmaken, basisinstellingen, afronden) en maakt een
long-lived token voor de app. Wachtwoord en token komen in de geheim-map en worden
nooit teruggegeven aan de aanroeper behalve het token zelf, en nooit gelogd.
Dit moet meteen na de eerste start gebeuren: een niet-ingerichte Home Assistant
koppelt sommige gevonden apparaten zonder te vragen.
"""
from __future__ import annotations

import asyncio
import logging
import os
import secrets
from typing import Optional

import aiohttp

from .ha_client import HAFout

log = logging.getLogger(__name__)
CLIENT_ID = "http://stroomdijk.local:8090/"


def _bewaar(pad: str, waarde: str, eigenaar: Optional[int]) -> None:
    fd = os.open(pad, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(waarde + "\n")
    if eigenaar is not None:
        os.chown(pad, eigenaar, eigenaar)


async def _wacht_op_ha(s: aiohttp.ClientSession, url: str, pogingen: int, pauze: float) -> list:
    for _ in range(pogingen):
        try:
            async with s.get(f"{url}/api/onboarding") as r:
                if r.status == 200:
                    return await r.json()
        except aiohttp.ClientError:
            pass
        await asyncio.sleep(pauze)
    raise HAFout(f"Home Assistant reageert niet op {url}")


async def richt_in(s: aiohttp.ClientSession, url: str, geheim_dir: str,
                   eigenaar: Optional[int] = None, pogingen: int = 90, pauze: float = 2) -> str:
    """Geeft het token terug. Doet niets als er al een token is."""
    token_pad = os.path.join(geheim_dir, "ha_token")
    if os.path.exists(token_pad):
        with open(token_pad) as f:
            return f.read().strip()

    stappen = {x["step"]: x["done"] for x in await _wacht_op_ha(s, url, pogingen, pauze)}
    if stappen.get("user"):
        raise HAFout("Home Assistant heeft al een eigenaar, maar er is geen token. "
                     "Niet automatisch op te lossen.")

    os.makedirs(geheim_dir, exist_ok=True)
    wachtwoord = secrets.token_urlsafe(24)
    _bewaar(os.path.join(geheim_dir, "ha_wachtwoord"), wachtwoord, eigenaar)  # eerst bewaren

    async with s.post(f"{url}/api/onboarding/users", json={
            "client_id": CLIENT_ID, "name": "Stroomdijk", "username": "stroomdijk",
            "password": wachtwoord, "language": "nl"}) as r:
        if r.status != 200:
            raise HAFout(f"eigenaar aanmaken mislukt: {r.status}")
        code = (await r.json())["auth_code"]

    async with s.post(f"{url}/auth/token", data={
            "grant_type": "authorization_code", "code": code, "client_id": CLIENT_ID}) as r:
        if r.status != 200:
            raise HAFout(f"inloggen mislukt: {r.status}")
        toegang = (await r.json())["access_token"]
    kop = {"Authorization": f"Bearer {toegang}"}

    for stap, body in (("core_config", {}), ("analytics", {}),
                       ("integration", {"client_id": CLIENT_ID, "redirect_uri": CLIENT_ID})):
        async with s.post(f"{url}/api/onboarding/{stap}", headers=kop, json=body) as r:
            if r.status != 200:
                log.warning("onboarding-stap %s gaf %s", stap, r.status)

    async with s.ws_connect(f"{url}/api/websocket") as ws:
        await ws.receive_json()
        await ws.send_json({"type": "auth", "access_token": toegang})
        if (await ws.receive_json()).get("type") != "auth_ok":
            raise HAFout("WebSocket-inloggen mislukt")
        await ws.send_json({"id": 1, "type": "auth/long_lived_access_token",
                            "client_name": "stroomdijk-app", "lifespan": 3650})
        m = await ws.receive_json()
        if not m.get("success"):
            raise HAFout("token maken mislukt")
        token = m["result"]
    _bewaar(token_pad, token, eigenaar)
    log.info("Home Assistant ingericht")
    return token


async def bevestig_http_config(client) -> bool:
    """Bevestigt een HTTP-config die Home Assistant op proef draait.

    Sinds 2026.11 zet Home Assistant de poort uit configuration.yaml eenmalig 'op proef'
    over naar zijn opslag. Wordt dat niet binnen 5 minuten bevestigd, dan valt hij terug
    op poort 8123. Op een kastje naast een andere Home Assistant botst dat. Zijn we via
    de proefconfig verbonden, dan werkt die dus: bevestigen. Geeft True als er iets
    bevestigd is.
    """
    try:
        cfg = await client.vraag("http/config")
    except HAFout as e:
        log.warning("http-config niet op te vragen: %s", e)
        return False
    pending = (cfg or {}).get("pending")
    if cfg.get("active_config_type") == "pending" and pending and not pending.get("error"):
        await client.vraag("http/config/promote")
        log.info("http-config van Home Assistant bevestigd (poort %s)", pending.get("server_port"))
        return True
    return False
