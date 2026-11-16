from stroomdijk.inrichten import bevestig_http_config


async def test_proefpoort_wordt_bevestigd(client, nep):
    assert await bevestig_http_config(client) is True
    assert nep.http["stable"]["server_port"] == 8124 and nep.http["pending"] is None
    assert await bevestig_http_config(client) is False      # tweede keer niets te doen


async def test_mislukte_proef_niet_bevestigen(client, nep):
    nep.http["pending"]["error"] = "not_promoted"
    assert await bevestig_http_config(client) is False
    assert nep.http["stable"]["server_port"] == 8123


async def test_draait_op_stabiel(client, nep):
    nep.http["active_config_type"] = "stable"
    assert await bevestig_http_config(client) is False
