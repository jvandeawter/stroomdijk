"""Start de Stroomdijk-app: python -m stroomdijk

Instellingen via omgevingsvariabelen (zie config.py). Met STROOMDIJK_DEMO=1 draait
hij met nepwaarden en zonder Home Assistant.
"""
from __future__ import annotations

import asyncio
import logging
import os
import signal

import aiohttp
from aiohttp import web

from .config import Instellingen, Status
from .demo import DemoHuis
from .ha_client import HAClient
from .huis import Huis
from .inrichten import bevestig_http_config, richt_in
from .ontdekken import laad_integraties
from .web import maak_app

log = logging.getLogger("stroomdijk")


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    inst = Instellingen.uit_omgeving()
    session = aiohttp.ClientSession()
    client = None

    if os.environ.get("STROOMDIJK_DEMO") == "1":
        log.info("demomodus: nepwaarden, geen Home Assistant")
        huis = DemoHuis()
        await huis.start()
    else:
        token = inst.lees_token()
        if not token:
            log.info("geen token gevonden, Home Assistant inrichten")
            token = await richt_in(session, inst.ha_url, inst.geheim_dir)
        client = HAClient(inst.ha_url, token, session)

        async def bevestig():
            await bevestig_http_config(client)
        client.bij_verbinden.append(bevestig)
        huis = Huis(client, Status.laad(inst.data_dir), laad_integraties())
        await huis.start()
        await client.start()

    runner = web.AppRunner(maak_app(huis))
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", inst.poort).start()
    log.info("Stroomdijk luistert op poort %s", inst.poort)

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    await stop.wait()

    log.info("stoppen")
    await runner.cleanup()
    if client is not None:
        await client.stop()
    await session.close()


if __name__ == "__main__":
    asyncio.run(main())
