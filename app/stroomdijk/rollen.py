"""Van Home Assistant-entiteiten naar rollen (net, zon, fasen) en naar één overzicht.

De app weet niet welk merk erachter zit. Per toegestane integratie staan regels in
integraties.json die zeggen welke sensor bij welke rol hoort. Zon mag meerdere bronnen
hebben (die tellen op); de net-rollen hebben er precies één.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional

ENKELVOUDIG = {"net_vermogen", "net_fase_l1", "net_fase_l2", "net_fase_l3",
               "spanning_l1", "spanning_l2", "spanning_l3",
               "net_afname_totaal", "net_teruglevering_totaal"}
ONBEKEND = {"unavailable", "unknown", "", None}


@dataclass
class Bron:
    rol: str
    entity_id: str
    integratie: str
    label: str
    apparaat: str = ""


def _past(regel: dict, ent: dict, attrs: dict) -> bool:
    if regel.get("device_class") and attrs.get("device_class") != regel["device_class"]:
        return False
    tk = ent.get("translation_key") or ""
    uid = ent.get("unique_id") or ""
    if tk and tk in regel.get("sleutel", []):
        return True
    return any(b in tk or b in uid for b in regel.get("bevat", []))


def zoek_rollen(integraties: Dict[str, dict], entries: List[dict], apparaten: List[dict],
                entiteiten: List[dict], states: Dict[str, dict]) -> Dict[str, List[Bron]]:
    domein = {e["entry_id"]: e["domain"] for e in entries}
    naam = {d["id"]: d.get("name_by_user") or d.get("name") or "" for d in apparaten}
    rollen: Dict[str, List[Bron]] = defaultdict(list)
    for ent in entiteiten:
        if ent.get("disabled_by"):
            continue
        dom = domein.get(ent.get("config_entry_id") or "") or ent.get("platform")
        cfg = integraties.get(dom or "")
        if not cfg:
            continue
        attrs = (states.get(ent["entity_id"]) or {}).get("attributes") or {}
        for regel in cfg.get("rollen", []):
            if _past(regel, ent, attrs):
                rollen[regel["rol"]].append(Bron(rol=regel["rol"], entity_id=ent["entity_id"],
                                                 integratie=dom, label=cfg.get("label", cfg["naam"]),
                                                 apparaat=naam.get(ent.get("device_id") or "", "")))
                break
    return dict(rollen)


def kies(rollen: Dict[str, List[Bron]], keuze: Dict[str, str]) -> Dict[str, List[Bron]]:
    """Eén bron per enkelvoudige rol: de gekozen, anders de eerste."""
    uit = {}
    for rol, bronnen in rollen.items():
        if rol in ENKELVOUDIG and len(bronnen) > 1:
            gekozen = [b for b in bronnen if b.entity_id == keuze.get(rol)]
            bronnen = gekozen or bronnen[:1]
        uit[rol] = bronnen
    return uit


def entiteiten_van(rollen: Dict[str, List[Bron]]) -> set:
    return {b.entity_id for bronnen in rollen.values() for b in bronnen}


def _getal(state: Optional[dict]) -> Optional[float]:
    if not state or state.get("state") in ONBEKEND:
        return None
    try:
        return float(state["state"])
    except (TypeError, ValueError):
        return None


def naar_watt(state: Optional[dict]) -> Optional[float]:
    v = _getal(state)
    if v is None:
        return None
    eenheid = (state.get("attributes") or {}).get("unit_of_measurement", "W")  # type: ignore[union-attr]
    return v * {"W": 1, "kW": 1000, "MW": 1_000_000}.get(eenheid, 1)


def naar_kwh(state: Optional[dict]) -> Optional[float]:
    v = _getal(state)
    if v is None:
        return None
    eenheid = (state.get("attributes") or {}).get("unit_of_measurement", "kWh")  # type: ignore[union-attr]
    return round(v * {"Wh": 0.001, "kWh": 1, "MWh": 1000}.get(eenheid, 1), 3)


def _som(waarden: List[Optional[float]]) -> Optional[float]:
    bekend = [w for w in waarden if w is not None]
    return sum(bekend) if bekend else None


def overzicht(rollen: Dict[str, List[Bron]], states: Dict[str, dict]) -> dict:
    """Het dashboard in getallen. Onderdelen zonder bron zijn None, zodat de tegel wegblijft."""
    def eerste(rol: str, omzetten=naar_watt) -> Optional[float]:
        b = rollen.get(rol)
        return omzetten(states.get(b[0].entity_id)) if b else None

    zon = None
    if rollen.get("zon_vermogen"):
        vandaag = {b.integratie: naar_kwh(states.get(b.entity_id)) for b in rollen.get("zon_vandaag", [])}
        bronnen = [{"label": b.label, "apparaat": b.apparaat, "integratie": b.integratie,
                    "w": naar_watt(states.get(b.entity_id)), "vandaag_kwh": vandaag.get(b.integratie),
                    "bijgewerkt": (states.get(b.entity_id) or {}).get("last_updated")}
                   for b in rollen["zon_vermogen"]]
        zon = {"w": _som([b["w"] for b in bronnen]),
               "vandaag_kwh": _som([b["vandaag_kwh"] for b in bronnen]),
               "bronnen": bronnen}

    net = None
    fasen = [{"fase": f"L{i}", "w": eerste(f"net_fase_l{i}"), "v": eerste(f"spanning_l{i}", _getal)}
             for i in (1, 2, 3)]
    if rollen.get("net_vermogen") or any(f["w"] is not None for f in fasen):
        w = eerste("net_vermogen")
        if w is None:
            w = _som([f["w"] for f in fasen])
        net = {"w": w,                         # plus is afname, min is teruglevering
               "fasen": [f for f in fasen if f["w"] is not None or f["v"] is not None],
               "afname_totaal_kwh": eerste("net_afname_totaal", naar_kwh),
               "teruglevering_totaal_kwh": eerste("net_teruglevering_totaal", naar_kwh)}

    huis = None
    if zon and net and zon["w"] is not None and net["w"] is not None:
        huis = zon["w"] + net["w"]
    return {"zon": zon, "net": net, "huis_w": huis}
