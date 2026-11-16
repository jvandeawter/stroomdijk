"""Demomodus: een nep-huis met bewegende waarden, zonder Home Assistant.

Handig om het dashboard te bekijken en te testen. Aan met STROOMDIJK_DEMO=1.
Levert precies dezelfde vorm als Huis.overzicht().
"""
from __future__ import annotations

import asyncio
import inspect
import math
import time
from typing import Callable, List, Optional


class DemoApparaten:
    async def lijst(self) -> dict:
        return {
            "gevonden": [{"integratie": "enphase_envoy", "naam": "Enphase Envoy", "omschrijving": "Zonnepanelen",
                          "flow_id": "demo", "bron": "zeroconf", "info": {"serial": "000000000000"}}],
            "gekoppeld": [{"integratie": "homewizard", "naam": "HomeWizard", "omschrijving": "Slimme meter",
                           "titel": "P1-meter", "entry_id": "demo", "status": "loaded"}],
            "handmatig": [{"integratie": "solaredge", "naam": "SolarEdge", "omschrijving": "Zonnepanelen",
                           "flow_id": "", "bron": "handmatig", "info": {}}],
            "niet_ondersteund": [{"naam": "Anker Solarbank", "omschrijving": "Thuisbatterij",
                                  "reden": "Er is nog geen officiële koppeling."}],
        }


class DemoHuis:
    def __init__(self, interval: float = 2.0):
        self.interval = interval
        self.luisteraars: List[Callable] = []
        self._taak: Optional[asyncio.Task] = None
        self._t0 = time.time()

    async def start(self) -> None:
        self._taak = asyncio.ensure_future(self._lus())

    async def stop(self) -> None:
        if self._taak:
            self._taak.cancel()

    async def _lus(self) -> None:
        while True:
            await asyncio.sleep(self.interval)
            for f in list(self.luisteraars):
                r = f()
                if inspect.isawaitable(r):
                    await r

    def overzicht(self) -> dict:
        t = time.time() - self._t0
        enphase = round(1380 + 60 * math.sin(t / 7))
        solaredge = 770
        net_w = round(940 + 160 * math.sin(t / 3.3)) - enphase - solaredge
        verdeling = (0.36, 0.31, 0.33)
        fasen = [{"fase": f"L{i + 1}", "w": round(net_w * s + (i - 1) * 90), "v": v}
                 for i, (s, v) in enumerate(zip(verdeling, (231.2, 229.8, 230.6)))]
        return {
            "zon": {"w": enphase + solaredge, "vandaag_kwh": 9.4, "bronnen": [
                {"label": "Enphase", "apparaat": "Envoy", "integratie": "enphase_envoy",
                 "w": enphase, "vandaag_kwh": 6.1, "bijgewerkt": None},
                {"label": "SolarEdge", "apparaat": "SolarEdge", "integratie": "solaredge",
                 "w": solaredge, "vandaag_kwh": 3.3, "bijgewerkt": None}]},
            "net": {"w": net_w, "fasen": fasen, "afname_totaal_kwh": 4213.6,
                    "teruglevering_totaal_kwh": 2876.1},
            "huis_w": enphase + solaredge + net_w,
            "verbonden": True, "fout": None, "demo": True,
        }
