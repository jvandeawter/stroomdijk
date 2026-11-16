"""Start de setup: python -m stroomdijk_setup

STROOMDIJK_SETUP_TEST=1  hotspot meteen starten, ook als er al netwerk is (alleen om te testen)
STROOMDIJK_SETUP_POORT   standaard 8091
STROOMDIJK_WIFI          standaard wlan0
"""
from __future__ import annotations

import asyncio
import logging
import os
import signal

from aiohttp import web

from .netwerk import NetworkManager
from .regelaar import Regelaar
from .web import maak_app

log = logging.getLogger("stroomdijk_setup")


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    # access log uit: niets van wat de klant intypt mag ooit in een log belanden
    logging.getLogger("aiohttp.access").setLevel(logging.WARNING)
    test = os.environ.get("STROOMDIJK_SETUP_TEST") == "1"
    poort = int(os.environ.get("STROOMDIJK_SETUP_POORT", "8091"))
    regelaar = Regelaar(NetworkManager(os.environ.get("STROOMDIJK_WIFI", "wlan0")), testmodus=test)

    runner = web.AppRunner(maak_app(regelaar))
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", poort).start()
    log.info("instelpagina op poort %s%s", poort, " (testmodus)" if test else "")
    try:
        await regelaar.start()
    except Exception:  # noqa: BLE001
        log.exception("setup kon niet starten")
        regelaar.toestand = "fout"
        regelaar.melding = "De setup kon niet bij de netwerkinstellingen."
    log.info("toestand: %s", regelaar.toestand)

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    await stop.wait()
    log.info("stoppen, hotspot uit")
    try:
        await regelaar.stop()
    except Exception:  # noqa: BLE001
        log.exception("hotspot stoppen mislukt")
    await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
