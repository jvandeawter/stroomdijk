"""Wanneer start de hotspot, en wat gebeurt er als de klant een wifi kiest.

Toestanden: start, wifi_uit, klaar (er is al netwerk), hotspot, verbinden, verbonden,
mislukt (hotspot draait weer, met melding), gestopt.
"""
from __future__ import annotations

import asyncio
import logging
from typing import List, Optional

from .netwerk import ontdubbel

log = logging.getLogger(__name__)


def hotspot_naam(hw_adres: str) -> str:
    staart = hw_adres.replace(":", "").upper()[-4:] or "0000"
    return f"Stroomdijk-{staart}"


class Regelaar:
    def __init__(self, nm, testmodus: bool = False, wacht_zonder_netwerk: float = 120,
                 controle_interval: float = 5, pauze: float = 2):
        self.nm = nm
        self.testmodus = testmodus
        self.wacht_zonder_netwerk = wacht_zonder_netwerk
        self.controle_interval = controle_interval
        self.pauze = pauze
        self.toestand = "start"
        self.melding = ""
        self.ssid = ""
        self.gekozen: Optional[str] = None
        self.netwerken: List[dict] = []
        self._taak: Optional[asyncio.Task] = None

    def status(self) -> dict:
        return {"toestand": self.toestand, "melding": self.melding, "hotspot": self.ssid,
                "gekozen": self.gekozen, "netwerken": self.netwerken, "testmodus": self.testmodus}

    async def start(self) -> None:
        await self.nm.open()
        self.ssid = hotspot_naam(await self.nm.hw_adres())
        if not await self.nm.wifi_aan():
            self.toestand = "wifi_uit"
            self.melding = "Wifi staat uit op dit kastje."
            return
        if not self.testmodus:
            # Alleen een hotspot als er echt geen netwerk is, niet bij een korte hapering.
            stappen = max(1, int(self.wacht_zonder_netwerk / self.controle_interval))
            for _ in range(stappen):
                if await self.nm.heeft_netwerk():
                    self.toestand = "klaar"
                    return
                await asyncio.sleep(self.controle_interval)
            if await self.nm.heeft_netwerk():
                self.toestand = "klaar"
                return
        await self._hotspot()

    async def _hotspot(self) -> None:
        self.netwerken = ontdubbel(await self.nm.scan(), self.ssid)
        await self.nm.start_hotspot(self.ssid)
        self.toestand = "hotspot"

    async def verbind(self, ssid: str, wachtwoord: str) -> None:
        if self.toestand not in ("hotspot", "mislukt"):
            raise ValueError(f"nu niet mogelijk (toestand {self.toestand})")
        if not ssid:
            raise ValueError("kies een netwerk")
        self.toestand = "verbinden"
        self.gekozen = ssid
        self.melding = ""
        self._taak = asyncio.ensure_future(self._verbind(ssid, wachtwoord))

    async def _verbind(self, ssid: str, wachtwoord: str) -> None:
        await asyncio.sleep(self.pauze)          # laat het antwoord eerst naar de telefoon gaan
        try:
            await self.nm.stop_hotspot()
            gelukt, reden = await self.nm.verbind(ssid, wachtwoord)
        except Exception as e:  # noqa: BLE001
            gelukt, reden = False, f"Er ging iets mis: {type(e).__name__}"
        if gelukt:
            self.toestand = "verbonden"
            self.melding = f"Stroomdijk is verbonden met {ssid}."
            log.info("verbonden met de gekozen wifi")
            return
        log.info("verbinden mislukt, hotspot weer aan")
        await self._hotspot()
        self.toestand = "mislukt"
        self.melding = reden

    async def wacht(self) -> None:
        if self._taak:
            await self._taak

    async def stop(self) -> None:
        if self.toestand in ("hotspot", "mislukt"):
            await self.nm.stop_hotspot()
        self.toestand = "gestopt"
