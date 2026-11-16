"""Apparaten koppelen door de config flow van Home Assistant te doorlopen.

Home Assistant bepaalt per stap welke velden nodig zijn. Stroomdijk vertaalt dat naar
een eenvoudig formulier. Wat de klant invult gaat rechtstreeks naar Home Assistant;
Stroomdijk bewaart het niet. Stroomdijk onthoudt alleen welke koppelingen hij zelf
maakte, zodat hij die (en alleen die) later weer kan verwijderen.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .config import Status
from .ha_client import HAClient, HAFout

LABELS = {
    "host": "Adres van het apparaat",
    "ip_address": "Adres van het apparaat",
    "username": "Gebruikersnaam of e-mailadres",
    "email": "E-mailadres",
    "password": "Wachtwoord",
    "site_id": "Site-ID",
    "api_key": "API-sleutel",
    "name": "Naam",
}

FOUTEN = {
    "invalid_auth": "Inloggen lukt niet. Klopt het wachtwoord?",
    "cannot_connect": "Het apparaat reageert niet. Staat het aan en zit het op hetzelfde netwerk?",
    "unknown": "Er ging iets onverwachts mis. Probeer het nog eens.",
    "already_configured": "Dit apparaat is al gekoppeld.",
    "already_in_progress": "Dit apparaat wordt al gekoppeld.",
}


@dataclass
class Veld:
    naam: str
    label: str
    soort: str = "tekst"          # tekst, wachtwoord, getal, keuze, vinkje
    verplicht: bool = False
    standaard: Any = None
    opties: List[Any] = field(default_factory=list)


@dataclass
class Stap:
    soort: str                    # formulier, klaar, afgebroken
    flow_id: str = ""
    stap_id: str = ""
    velden: List[Veld] = field(default_factory=list)
    fouten: Dict[str, str] = field(default_factory=dict)
    info: Dict[str, str] = field(default_factory=dict)
    entry_id: str = ""
    titel: str = ""
    reden: str = ""


def _veld(schema: dict) -> Veld:
    naam = schema.get("name", "")
    v = Veld(naam=naam, label=LABELS.get(naam, naam.replace("_", " ").capitalize()),
             verplicht=bool(schema.get("required")), standaard=schema.get("default"))
    sel = schema.get("selector") or {}
    soort = schema.get("type")
    if "text" in sel:
        v.soort = "wachtwoord" if (sel["text"] or {}).get("type") == "password" else "tekst"
    elif "number" in sel or soort in ("integer", "float"):
        v.soort = "getal"
    elif "boolean" in sel or soort == "boolean":
        v.soort = "vinkje"
    elif "select" in sel or soort == "select":
        v.soort = "keuze"
        opties = (sel.get("select") or {}).get("options") or schema.get("options") or []
        v.opties = [o.get("value") if isinstance(o, dict) else (o[0] if isinstance(o, (list, tuple)) else o)
                    for o in opties]
    if "password" in naam and v.soort == "tekst":
        v.soort = "wachtwoord"
    return v


def vertaal(r: dict) -> Stap:
    """Zet een antwoord van de Home Assistant flow-API om naar een Stap."""
    soort = r.get("type")
    if soort == "form":
        return Stap(soort="formulier", flow_id=r.get("flow_id", ""), stap_id=r.get("step_id", ""),
                    velden=[_veld(s) for s in r.get("data_schema") or []],
                    fouten={k: FOUTEN.get(v, v) for k, v in (r.get("errors") or {}).items()},
                    info={k: str(v) for k, v in (r.get("description_placeholders") or {}).items()})
    if soort == "create_entry":
        res = r.get("result") or {}
        entry_id = res.get("entry_id", "") if isinstance(res, dict) else ""
        return Stap(soort="klaar", flow_id=r.get("flow_id", ""), entry_id=entry_id,
                    titel=r.get("title") or (res.get("title", "") if isinstance(res, dict) else ""))
    if soort == "abort":
        reden = r.get("reason", "")
        return Stap(soort="afgebroken", flow_id=r.get("flow_id", ""), reden=FOUTEN.get(reden, reden))
    # menu, external, progress: nog niet ondersteund in prototype 1
    return Stap(soort="afgebroken", flow_id=r.get("flow_id", ""),
                reden=f"Deze stap ({soort}) kan Stroomdijk nog niet tonen.")


class Koppelaar:
    def __init__(self, client: HAClient, status: Status, integraties: Dict[str, dict]):
        self.client = client
        self.status = status
        self.integraties = integraties

    def _toegestaan(self, integratie: str) -> None:
        if integratie not in self.integraties:
            raise HAFout(f"integratie {integratie} staat niet op de lijst")

    async def start(self, integratie: str, flow_id: Optional[str] = None) -> Stap:
        """Gevonden apparaat (met flow_id) of met de hand toevoegen (zonder)."""
        self._toegestaan(integratie)
        if flow_id:
            r = await self.client.rest("GET", f"/api/config/config_entries/flow/{flow_id}")
            if r.get("handler") not in (None, integratie):
                raise HAFout("flow hoort niet bij deze integratie")
        else:
            r = await self.client.rest("POST", "/api/config/config_entries/flow",
                                       {"handler": integratie, "show_advanced_options": False})
        return self._na(r)

    async def stuur(self, flow_id: str, invoer: Dict[str, Any]) -> Stap:
        r = await self.client.rest("POST", f"/api/config/config_entries/flow/{flow_id}", invoer)
        return self._na(r)

    async def annuleer(self, flow_id: str) -> None:
        await self.client.rest("DELETE", f"/api/config/config_entries/flow/{flow_id}")

    def _na(self, r: dict) -> Stap:
        stap = vertaal(r)
        if stap.soort == "klaar" and stap.entry_id:
            self.status.koppeling_gemaakt(stap.entry_id)
        return stap

    async def verwijder_eigen(self) -> List[str]:
        """Verwijdert alleen koppelingen die Stroomdijk zelf maakte."""
        weg = []
        for entry_id in list(self.status.eigen_koppelingen):
            try:
                await self.client.rest("DELETE", f"/api/config/config_entries/entry/{entry_id}")
            except HAFout as e:
                if "404" not in str(e):
                    raise
            self.status.koppeling_weg(entry_id)
            weg.append(entry_id)
        return weg
