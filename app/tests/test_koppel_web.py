import asyncio

from conftest import wacht_tot
from stroomdijk.demo import DemoApparaten, DemoHuis
from stroomdijk.huis import Huis
from stroomdijk.koppelen import Koppelaar
from stroomdijk.ontdekken import Apparatenlijst
from stroomdijk.web import maak_app


async def maak(aiohttp_client, client, status, integraties):
    huis = Huis(client, status, integraties)
    await huis.start()
    await huis.ververs()
    app = maak_app(huis, Apparatenlijst(client, integraties), Koppelaar(client, status, integraties))
    return huis, await aiohttp_client(app)


async def test_hele_route_envoy(aiohttp_client, client, nep, status, integraties):
    fid = nep.ontdek("enphase_envoy", serial="1234", host="192.0.2.10")
    huis, c = await maak(aiohttp_client, client, status, integraties)

    assert (await c.get(f"/koppelen?integratie=enphase_envoy&flow={fid}")).status == 200
    stap = await (await c.post("/api/koppelen", json={"integratie": "enphase_envoy", "flow_id": fid})).json()
    assert stap["soort"] == "formulier"
    assert [v["soort"] for v in stap["velden"]] == ["tekst", "tekst", "wachtwoord"]

    fout = await (await c.post(f"/api/koppelen/{fid}", json={"invoer": {"host": "x", "password": "fout"}})).json()
    assert fout["soort"] == "formulier" and "wachtwoord" in fout["fouten"]["base"]

    klaar = await (await c.post(f"/api/koppelen/{fid}", json={"invoer": {"host": "x", "password": "goed"}})).json()
    assert klaar["soort"] == "klaar" and klaar["entry_id"] in status.eigen_koppelingen

    await wacht_tot(lambda: huis.overzicht()["zon"] is not None)
    d = await (await c.get("/api/apparaten")).json()
    assert [g["naam"] for g in d["gekoppeld"]] == ["Enphase Envoy"] and d["gevonden"] == []


async def test_handmatig_en_annuleren(aiohttp_client, client, nep, status, integraties):
    _, c = await maak(aiohttp_client, client, status, integraties)
    stap = await (await c.post("/api/koppelen", json={"integratie": "solaredge"})).json()
    assert stap["soort"] == "formulier" and stap["flow_id"] in nep.flows
    assert (await c.delete(f"/api/koppelen/{stap['flow_id']}")).status == 200
    assert stap["flow_id"] not in nep.flows


async def test_niet_toegestaan_en_onbekende_flow(aiohttp_client, client, status, integraties):
    _, c = await maak(aiohttp_client, client, status, integraties)
    r = await c.post("/api/koppelen", json={"integratie": "sonos"})
    assert r.status == 502 and "niet op de lijst" in (await r.json())["fout"]
    r = await c.post("/api/koppelen/bestaatniet", json={"invoer": {"password": "geheim123"}})
    assert r.status == 502 and "geheim123" not in await r.text()


async def test_eigen_koppelingen_verwijderen(aiohttp_client, client, nep, status, integraties):
    huis, c = await maak(aiohttp_client, client, status, integraties)
    stap = await (await c.post("/api/koppelen", json={"integratie": "solaredge"})).json()
    await c.post(f"/api/koppelen/{stap['flow_id']}", json={"invoer": {"site_id": "1", "api_key": "x"}})
    await wacht_tot(lambda: huis.overzicht()["zon"] is not None)
    d = await (await c.post("/api/koppelingen/eigen/verwijderen")).json()
    assert len(d["verwijderd"]) == 1
    assert {e["domain"] for e in nep.entries} == {"mqtt"}
    await wacht_tot(lambda: huis.overzicht()["zon"] is None)


async def test_demo_koppelt_niet(aiohttp_client):
    c = await aiohttp_client(maak_app(DemoHuis(), DemoApparaten()))
    r = await c.post("/api/koppelen", json={"integratie": "solaredge"})
    assert r.status == 404
    await asyncio.sleep(0)
