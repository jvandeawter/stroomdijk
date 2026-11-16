import pytest

from conftest import wacht_tot
from stroomdijk.ha_client import AuthFout, HAClient, HAFout


async def test_vraag(client):
    entries = await client.vraag("config_entries/get")
    assert entries[0]["domain"] == "mqtt"


async def test_onbekende_opdracht_geeft_fout(client):
    with pytest.raises(HAFout, match="unknown_command"):
        await client.vraag("bestaat/niet")


async def test_verkeerd_token(url):
    c = HAClient(url, "fout-token", timeout=2, min_wacht=0.05, max_wacht=0.1)
    await c.start()
    await wacht_tot(lambda: c.fout is not None)
    assert "token geweigerd" in c.fout
    assert "fout-token" not in c.fout          # token nooit in een melding
    assert not c.verbonden
    await c.stop()


async def test_niet_bereikbaar():
    c = HAClient("http://127.0.0.1:1", "x", timeout=1, min_wacht=0.05, max_wacht=0.1)
    await c.start()
    await wacht_tot(lambda: c.fout is not None)
    assert not c.verbonden
    with pytest.raises(HAFout):
        await c.vraag("get_states")
    await c.stop()


async def test_abonnement_en_herverbinden(client, nep):
    ontvangen = []
    await client.abonneer("s", {"type": "subscribe_events", "event_type": "state_changed"},
                          lambda ev: ontvangen.append(ev["data"]["entity_id"]))
    await nep.zet("sensor.a", 1)
    await wacht_tot(lambda: ontvangen == ["sensor.a"])

    await nep.verbreek_alles()
    await wacht_tot(lambda: not client.verbonden)
    await client.wacht_op_verbinding(3)
    await wacht_tot(lambda: len(nep.abos) == 1)   # abonnement vanzelf opnieuw opgezet
    await nep.zet("sensor.b", 2)
    await wacht_tot(lambda: ontvangen == ["sensor.a", "sensor.b"])


async def test_rest_met_verkeerd_token(url):
    c = HAClient(url, "fout-token", timeout=2)
    await c.start()
    with pytest.raises(AuthFout):
        await c.rest("POST", "/api/config/config_entries/flow", {"handler": "solaredge"})
    await c.stop()
