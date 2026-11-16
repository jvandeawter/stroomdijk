from conftest import wacht_tot
from stroomdijk import rollen as R
from stroomdijk.huis import Huis
from stroomdijk.koppelen import Koppelaar


async def koppel(client, status, integraties, nep, handler, invoer):
    fid = nep.ontdek(handler)
    k = Koppelaar(client, status, integraties)
    await k.start(handler, fid)
    return await k.stuur(fid, invoer)


async def test_leeg_huis(client, status, integraties):
    h = Huis(client, status, integraties)
    await h.start()
    await h.ververs()
    o = h.overzicht()
    assert o["zon"] is None and o["net"] is None and o["huis_w"] is None
    assert o["verbonden"]


async def test_dashboard_vult_zich_na_koppelen(client, nep, status, integraties):
    h = Huis(client, status, integraties)
    await h.start()
    await h.ververs()
    await koppel(client, status, integraties, nep, "enphase_envoy", {"host": "x", "password": "goed"})
    await wacht_tot(lambda: h.overzicht()["zon"] is not None)   # via entity_registry_updated

    o = h.overzicht()
    assert o["zon"]["w"] == 1234                  # kW omgerekend naar W, omvormer niet dubbel
    assert o["zon"]["vandaag_kwh"] == 5.6         # Wh omgerekend naar kWh
    assert o["zon"]["bronnen"][0]["label"] == "Enphase"
    assert o["net"] is None and o["huis_w"] is None

    await koppel(client, status, integraties, nep, "solaredge", {"site_id": "1", "api_key": "x"})
    await wacht_tot(lambda: len(h.overzicht()["zon"]["bronnen"]) == 2)
    assert h.overzicht()["zon"]["w"] == 1234 + 770


async def test_live_waarden_en_onbekend(client, nep, status, integraties):
    h = Huis(client, status, integraties)
    await h.start()
    await koppel(client, status, integraties, nep, "enphase_envoy", {"password": "goed"})
    await wacht_tot(lambda: h.overzicht()["zon"] is not None)
    await nep.zet("sensor.envoy_1234_huidige_opwek", "2.5")
    await wacht_tot(lambda: h.overzicht()["zon"]["w"] == 2500)
    await nep.zet("sensor.envoy_1234_huidige_opwek", "unavailable")
    await wacht_tot(lambda: h.overzicht()["zon"]["w"] is None)


async def test_net_en_huisverbruik(client, nep, status, integraties):
    h = Huis(client, status, integraties)
    await h.start()
    await koppel(client, status, integraties, nep, "enphase_envoy", {"password": "goed"})
    await koppel(client, status, integraties, nep, "homewizard", {})
    await wacht_tot(lambda: h.overzicht()["net"] is not None and h.overzicht()["zon"] is not None)
    o = h.overzicht()
    assert o["net"]["w"] == -500                  # teruglevering
    assert [f["w"] for f in o["net"]["fasen"]] == [-300, -100, -100]
    assert [f["v"] for f in o["net"]["fasen"]] == [230.1] * 3
    assert o["huis_w"] == 1234 - 500


def test_bronkeuze_enkelvoudig():
    b = lambda e: R.Bron("net_vermogen", e, "homewizard", "P1")  # noqa: E731
    rollen = {"net_vermogen": [b("sensor.a"), b("sensor.b")], "zon_vermogen": [b("z1"), b("z2")]}
    assert [x.entity_id for x in R.kies(rollen, {})["net_vermogen"]] == ["sensor.a"]
    assert [x.entity_id for x in R.kies(rollen, {"net_vermogen": "sensor.b"})["net_vermogen"]] == ["sensor.b"]
    assert len(R.kies(rollen, {})["zon_vermogen"]) == 2


def test_eenheden():
    st = lambda s, u: {"state": s, "attributes": {"unit_of_measurement": u}}  # noqa: E731
    assert R.naar_watt(st("1.5", "kW")) == 1500
    assert R.naar_watt(st("abc", "W")) is None
    assert R.naar_kwh(st("1", "MWh")) == 1000
    assert R.naar_watt(None) is None
