import os

import aiohttp
import pytest

from nep_ha import LLAT, NepHA
from stroomdijk.ha_client import HAFout
from stroomdijk.inrichten import richt_in


@pytest.fixture
def nep():
    return NepHA(onboarded=False)


async def test_lege_ha_inrichten(url, nep, tmp_path):
    geheim = str(tmp_path / "geheim")
    async with aiohttp.ClientSession() as s:
        token = await richt_in(s, url, geheim, pogingen=3, pauze=0.01)
    assert token == LLAT
    assert nep.gebruiker["username"] == "stroomdijk"
    wachtwoord = open(os.path.join(geheim, "ha_wachtwoord")).read().strip()
    assert nep.gebruiker["password"] == wachtwoord and len(wachtwoord) >= 30
    for naam in ("ha_token", "ha_wachtwoord"):
        pad = os.path.join(geheim, naam)
        assert oct(os.stat(pad).st_mode & 0o777) == "0o600"
        assert open(pad).read().endswith("\n")       # prompt plakt er niet achter


async def test_tweede_keer_doet_niets(url, nep, tmp_path):
    geheim = str(tmp_path)
    async with aiohttp.ClientSession() as s:
        eerste = await richt_in(s, url, geheim, pogingen=3, pauze=0.01)
        nep.gebruiker = None                        # zou opnieuw kunnen, maar mag niet
        tweede = await richt_in(s, url, geheim, pogingen=3, pauze=0.01)
    assert eerste == tweede
    assert nep.gebruiker is None


async def test_al_eigenaar_zonder_token(url, nep, tmp_path):
    nep.onboarded = True
    async with aiohttp.ClientSession() as s:
        with pytest.raises(HAFout, match="al een eigenaar"):
            await richt_in(s, url, str(tmp_path), pogingen=3, pauze=0.01)
