"""Welke energieapparaten heeft Home Assistant gevonden, en wat kun je met de hand toevoegen."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Dict, List

from .ha_client import HAClient

_PAD = os.path.join(os.path.dirname(__file__), "integraties.json")


def laad_integraties(pad: str = _PAD) -> Dict[str, dict]:
    with open(pad, encoding="utf-8") as f:
        data = json.load(f)
    return {k: v for k, v in data.items() if not k.startswith("_")}


@dataclass
class Gevonden:
    integratie: str
    naam: str
    omschrijving: str
    flow_id: str = ""            # leeg bij handmatig toevoegen
    bron: str = ""               # zeroconf, ssdp, dhcp, ... of "handmatig"
    info: Dict[str, str] = field(default_factory=dict)


def filter_flows(flows: List[dict], integraties: Dict[str, dict]) -> List[Gevonden]:
    """Houdt alleen de flows over die bij een toegestane energie-integratie horen."""
    uit: List[Gevonden] = []
    for f in flows:
        dom = f.get("handler")
        cfg = integraties.get(dom)
        ctx = f.get("context") or {}
        if cfg is None or ctx.get("source") in ("user", "reauth", "reconfigure"):
            continue
        info = {k: str(v) for k, v in (ctx.get("title_placeholders") or {}).items()}
        uit.append(Gevonden(integratie=dom, naam=cfg["naam"], omschrijving=cfg.get("omschrijving", ""),
                            flow_id=f["flow_id"], bron=ctx.get("source", ""), info=info))
    return uit


def handmatig(integraties: Dict[str, dict], gekoppeld: set) -> List[Gevonden]:
    """Integraties die je met de hand toevoegt (cloud), en die nog niet gekoppeld zijn."""
    return [Gevonden(integratie=d, naam=c["naam"], omschrijving=c.get("omschrijving", ""), bron="handmatig")
            for d, c in integraties.items() if c.get("handmatig") and d not in gekoppeld]


async def gevonden(client: HAClient, integraties: Dict[str, dict]) -> List[Gevonden]:
    flows = await client.vraag("config_entries/flow/progress")
    return filter_flows(flows or [], integraties)


async def gekoppelde_integraties(client: HAClient, integraties: Dict[str, dict]) -> List[dict]:
    entries = await client.vraag("config_entries/get")
    return [e for e in entries or [] if e.get("domain") in integraties]
