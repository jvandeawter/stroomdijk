import logging
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from stroomdijk_setup.netwerk import ontdubbel  # noqa: E402
from stroomdijk_setup.regelaar import Regelaar, hotspot_naam  # noqa: E402
from stroomdijk_setup.web import maak_app  # noqa: E402

GOED = "juist-wachtwoord"


class NepNM:
    def __init__(self, netwerk=True, wifi=True):
        self.netwerk = netwerk
        self.wifi = wifi
        self.hotspot = None
        self.verbonden = None
        self.log = []

    async def open(self):
        self.log.append("open")

    async def wifi_aan(self):
        return self.wifi

    async def heeft_netwerk(self):
        return self.netwerk

    async def hw_adres(self):
        return "2C:CF:67:56:32:AC"

    async def scan(self):
        return [{"ssid": "Thuis", "sterkte": 40, "beveiligd": True},
                {"ssid": "Thuis", "sterkte": 80, "beveiligd": True},
                {"ssid": "", "sterkte": 90, "beveiligd": False},
                {"ssid": "Stroomdijk-32AC", "sterkte": 99, "beveiligd": False},
                {"ssid": "Buren", "sterkte": 20, "beveiligd": True}]

    async def start_hotspot(self, ssid):
        self.hotspot = ssid
        self.log.append("hotspot aan")

    async def stop_hotspot(self):
        self.hotspot = None
        self.log.append("hotspot uit")

    async def verbind(self, ssid, wachtwoord):
        self.log.append(f"verbind {ssid}")
        if wachtwoord == GOED:
            self.verbonden = ssid
            return True, ""
        return False, "Verbinden lukte niet."


def regelaar(nm, **kw):
    return Regelaar(nm, wacht_zonder_netwerk=0.05, controle_interval=0.01, pauze=0, **kw)


def test_hotspot_naam_en_ontdubbelen():
    assert hotspot_naam("2C:CF:67:56:32:AC") == "Stroomdijk-32AC"
    lijst = ontdubbel([{"ssid": "A", "sterkte": 10}, {"ssid": "A", "sterkte": 50}, {"ssid": "", "sterkte": 9},
                       {"ssid": "B", "sterkte": 70}, {"ssid": "Eigen", "sterkte": 99}], "Eigen")
    assert [(n["ssid"], n["sterkte"]) for n in lijst] == [("B", 70), ("A", 50)]


async def test_met_netwerk_geen_hotspot():
    nm = NepNM(netwerk=True)
    r = regelaar(nm)
    await r.start()
    assert r.toestand == "klaar" and nm.hotspot is None


async def test_zonder_netwerk_hotspot():
    nm = NepNM(netwerk=False)
    r = regelaar(nm)
    await r.start()
    assert r.toestand == "hotspot" and nm.hotspot == "Stroomdijk-32AC"
    assert [n["ssid"] for n in r.netwerken] == ["Thuis", "Buren"]       # zonder eigen hotspot en lege naam


async def test_testmodus_start_hotspot_ook_met_netwerk():
    nm = NepNM(netwerk=True)
    r = regelaar(nm, testmodus=True)
    await r.start()
    assert r.toestand == "hotspot"


async def test_wifi_uit():
    nm = NepNM(wifi=False)
    r = regelaar(nm, testmodus=True)
    await r.start()
    assert r.toestand == "wifi_uit" and nm.hotspot is None


async def test_verbinden_gelukt():
    nm = NepNM(netwerk=False)
    r = regelaar(nm)
    await r.start()
    await r.verbind("Thuis", GOED)
    await r.wacht()
    assert r.toestand == "verbonden" and nm.verbonden == "Thuis" and nm.hotspot is None
    assert nm.log[-2:] == ["hotspot uit", "verbind Thuis"]


async def test_verbinden_mislukt_hotspot_weer_aan():
    nm = NepNM(netwerk=False)
    r = regelaar(nm)
    await r.start()
    await r.verbind("Thuis", "fout")
    await r.wacht()
    assert r.toestand == "mislukt" and nm.hotspot == "Stroomdijk-32AC" and "lukte niet" in r.melding
    await r.verbind("Thuis", GOED)                # opnieuw proberen mag
    await r.wacht()
    assert r.toestand == "verbonden"


async def test_verbinden_kan_niet_als_er_al_netwerk_is():
    r = regelaar(NepNM(netwerk=True))
    await r.start()
    with pytest.raises(ValueError):
        await r.verbind("Thuis", GOED)


async def test_web_route_zonder_wachtwoord_in_log(aiohttp_client, caplog):
    caplog.set_level(logging.DEBUG)
    nm = NepNM(netwerk=False)
    r = regelaar(nm, testmodus=True)
    await r.start()
    c = await aiohttp_client(maak_app(r))
    assert (await c.get("/")).status == 200
    s = await (await c.get("/api/status")).json()
    assert s["toestand"] == "hotspot" and s["hotspot"] == "Stroomdijk-32AC" and s["testmodus"]

    resp = await c.post("/api/verbind", json={"ssid": "Thuis", "wachtwoord": GOED})
    assert resp.status == 202
    await r.wacht()
    assert (await (await c.get("/api/status")).json())["toestand"] == "verbonden"
    assert GOED not in caplog.text
    assert "wachtwoord" not in (await (await c.get("/api/status")).text())

    resp = await c.post("/api/verbind", json={"ssid": "Thuis", "wachtwoord": GOED})
    assert resp.status == 409                     # al verbonden


async def test_stop_zet_hotspot_uit(aiohttp_client):
    nm = NepNM(netwerk=False)
    r = regelaar(nm, testmodus=True)
    await r.start()
    c = await aiohttp_client(maak_app(r))
    await c.post("/api/stop")
    assert nm.hotspot is None and r.toestand == "gestopt"
