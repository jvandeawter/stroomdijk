from stroomdijk.demo import DemoApparaten, DemoHuis
from stroomdijk.huis import Huis
from stroomdijk.koppelen import Koppelaar
from stroomdijk.ontdekken import Apparatenlijst, laad_niet_ondersteund
from stroomdijk.web import maak_app


async def test_lijst_gevonden_handmatig_niet_ondersteund(client, nep, integraties):
    nep.ontdek("enphase_envoy", serial="1234", host="192.0.2.10")
    nep.ontdek("sonos", source="ssdp")
    nep.ontdek("unifi", source="integration_discovery", name="router")
    d = await Apparatenlijst(client, integraties).lijst()
    assert [g["integratie"] for g in d["gevonden"]] == ["enphase_envoy"]
    assert d["gevonden"][0]["info"]["host"] == "192.0.2.10"
    assert d["gekoppeld"] == []                                # mqtt telt niet mee
    assert [h["integratie"] for h in d["handmatig"]] == ["solaredge"]
    assert {n["naam"] for n in d["niet_ondersteund"]} >= {"Anker Solarbank", "Zonneplan Connect"}


async def test_na_koppelen_gekoppeld_en_niet_meer_handmatig(client, status, integraties):
    k = Koppelaar(client, status, integraties)
    stap = await k.start("solaredge")
    await k.stuur(stap.flow_id, {"site_id": "1", "api_key": "x"})
    d = await Apparatenlijst(client, integraties).lijst()
    assert [g["naam"] for g in d["gekoppeld"]] == ["SolarEdge"]
    assert d["handmatig"] == []


def test_niet_ondersteund_geen_integraties():
    from stroomdijk.ontdekken import laad_integraties
    assert "_niet_ondersteund" not in laad_integraties()
    assert all("reden" in n for n in laad_niet_ondersteund())


async def test_api_en_pagina(aiohttp_client, client, nep, status, integraties):
    nep.ontdek("enphase_envoy", serial="1234")
    c = await aiohttp_client(maak_app(Huis(client, status, integraties), Apparatenlijst(client, integraties)))
    r = await c.get("/apparaten")
    assert r.status == 200 and "Apparaten" in await r.text()
    d = await (await c.get("/api/apparaten")).json()
    assert d["gevonden"][0]["naam"] == "Enphase Envoy"
    assert (await c.get("/static/stijl.css")).status == 200


async def test_api_zonder_verbinding(aiohttp_client, url, status, integraties):
    from stroomdijk.ha_client import HAClient
    los = HAClient(url, "x")                                   # nooit gestart, dus niet verbonden
    c = await aiohttp_client(maak_app(DemoHuis(), Apparatenlijst(los, integraties)))
    r = await c.get("/api/apparaten")
    assert r.status == 503 and "niet verbonden" in (await r.json())["fout"]


async def test_demo_apparaten(aiohttp_client):
    c = await aiohttp_client(maak_app(DemoHuis(), DemoApparaten()))
    d = await (await c.get("/api/apparaten")).json()
    assert d["gevonden"] and d["gekoppeld"] and d["handmatig"] and d["niet_ondersteund"]
