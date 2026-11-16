"""Het levende beeld van het huis: rollen plus de laatste waarden, altijd bij.

Haalt bij elke (her)verbinding de registries en states op, luistert daarna alleen naar
wijzigingen (push) en herberekent de rollen als er entiteiten bijkomen of verdwijnen.
"""
from __future__ import annotations

import inspect
import logging
from typing import Callable, Dict, List

from . import rollen as R
from .config import Status
from .ha_client import HAClient

log = logging.getLogger(__name__)


class Huis:
    def __init__(self, client: HAClient, status: Status, integraties: Dict[str, dict]):
        self.client = client
        self.status = status
        self.integraties = integraties
        self.rollen: Dict[str, List[R.Bron]] = {}
        self.states: Dict[str, dict] = {}
        self.luisteraars: List[Callable] = []

    async def start(self) -> None:
        self.client.bij_verbinden.append(self.ververs)
        await self.client.abonneer("states", {"type": "subscribe_events", "event_type": "state_changed"},
                                   self._state)
        await self.client.abonneer("registry", {"type": "subscribe_events",
                                                "event_type": "entity_registry_updated"}, self._registry)

    async def ververs(self) -> None:
        entries = await self.client.vraag("config_entries/get")
        apparaten = await self.client.vraag("config/device_registry/list")
        entiteiten = await self.client.vraag("config/entity_registry/list")
        alle = {s["entity_id"]: s for s in await self.client.vraag("get_states")}
        self.rollen = R.kies(R.zoek_rollen(self.integraties, entries, apparaten, entiteiten, alle),
                             self.status.bronkeuze)
        self.states = {eid: alle.get(eid) for eid in R.entiteiten_van(self.rollen)}
        self._meld()

    def _state(self, ev: dict) -> None:
        data = ev.get("data") or {}
        eid = data.get("entity_id")
        if eid in self.states:
            self.states[eid] = data.get("new_state")
            self._meld()

    async def _registry(self, ev: dict) -> None:
        await self.ververs()

    def _meld(self) -> None:
        for f in self.luisteraars:
            try:
                r = f()
                if inspect.isawaitable(r):
                    import asyncio
                    asyncio.ensure_future(r)
            except Exception:  # noqa: BLE001
                log.exception("fout in luisteraar")

    def overzicht(self) -> dict:
        o = R.overzicht(self.rollen, self.states)
        o["verbonden"] = self.client.verbonden
        o["fout"] = self.client.fout
        return o
