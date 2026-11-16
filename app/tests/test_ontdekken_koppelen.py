import pytest

from stroomdijk.config import Status
from stroomdijk.ha_client import HAFout
from stroomdijk.koppelen import Koppelaar, vertaal
from stroomdijk.ontdekken import filter_flows, gevonden, handmatig


async def test_alleen_energie_apparaten(client, nep, integraties):
    nep.ontdek("enphase_envoy", serial="1234", host="192.0.2.10")
    nep.ontdek("sonos", source="ssdp")
    nep.ontdek("ipp", name="Printer")
    lijst = await gevonden(client, integraties)
    assert [g.integratie for g in lijst] == ["enphase_envoy"]
    assert lijst[0].naam == "Enphase Envoy" and lijst[0].info["serial"] == "1234"


def test_eigen_flows_tellen_niet_als_gevonden(integraties):
    flows = [{"flow_id": "1", "handler": "solaredge", "context": {"source": "user"}}]
    assert filter_flows(flows, integraties) == []


def test_handmatig(integraties):
    assert [g.integratie for g in handmatig(integraties, set())] == ["solaredge"]
    assert handmatig(integraties, {"solaredge"}) == []


def test_vertaal_velden():
    stap = vertaal({"type": "form", "flow_id": "f", "step_id": "user", "errors": {"base": "invalid_auth"},
                    "data_schema": [
                        {"name": "host", "required": True, "type": "string"},
                        {"name": "password", "type": "string"},
                        {"name": "api_key", "selector": {"text": {"type": "password"}}},
                        {"name": "poort", "selector": {"number": {}}},
                        {"name": "modus", "selector": {"select": {"options": [{"value": "a"}, "b"]}}},
                    ]})
    soorten = {v.naam: v.soort for v in stap.velden}
    assert soorten == {"host": "tekst", "password": "wachtwoord", "api_key": "wachtwoord",
                       "poort": "getal", "modus": "keuze"}
    assert stap.velden[0].label == "Adres van het apparaat" and stap.velden[0].verplicht
    assert stap.velden[4].opties == ["a", "b"]
    assert "wachtwoord" in stap.fouten["base"]


def test_vertaal_onbekende_stap():
    assert vertaal({"type": "menu", "flow_id": "f"}).soort == "afgebroken"


async def test_gevonden_apparaat_koppelen(client, nep, status, integraties):
    fid = nep.ontdek("enphase_envoy", serial="1234")
    k = Koppelaar(client, status, integraties)
    stap = await k.start("enphase_envoy", fid)
    assert stap.soort == "formulier" and [v.naam for v in stap.velden] == ["host", "username", "password"]

    stap = await k.stuur(fid, {"host": "192.0.2.10", "username": "a@b.nl", "password": "fout"})
    assert stap.soort == "formulier" and "base" in stap.fouten

    stap = await k.stuur(fid, {"host": "192.0.2.10", "username": "a@b.nl", "password": "goed"})
    assert stap.soort == "klaar" and stap.entry_id
    assert status.eigen_koppelingen == [stap.entry_id]
    assert Status.laad(str(status.pad).rsplit("/", 1)[0]).eigen_koppelingen == [stap.entry_id]


async def test_handmatig_toevoegen(client, status, integraties):
    k = Koppelaar(client, status, integraties)
    stap = await k.start("solaredge")
    assert [v.soort for v in stap.velden] == ["tekst", "wachtwoord"]
    stap = await k.stuur(stap.flow_id, {"site_id": "1", "api_key": "x"})
    assert stap.soort == "klaar"


async def test_niet_toegestane_integratie(client, status, integraties):
    with pytest.raises(HAFout, match="niet op de lijst"):
        await Koppelaar(client, status, integraties).start("sonos")


async def test_verwijder_alleen_eigen(client, nep, status, integraties):
    k = Koppelaar(client, status, integraties)
    stap = await k.start("solaredge")
    await k.stuur(stap.flow_id, {"site_id": "1", "api_key": "x"})
    assert {e["domain"] for e in nep.entries} == {"mqtt", "solaredge"}
    await k.verwijder_eigen()
    assert {e["domain"] for e in nep.entries} == {"mqtt"}      # bestaande koppeling blijft
    assert status.eigen_koppelingen == []
