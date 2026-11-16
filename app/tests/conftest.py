import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from nep_ha import TOKEN, NepHA  # noqa: E402
from stroomdijk.config import Status  # noqa: E402
from stroomdijk.ha_client import HAClient  # noqa: E402
from stroomdijk.ontdekken import laad_integraties  # noqa: E402


@pytest.fixture
def nep():
    return NepHA()


@pytest.fixture
async def server(aiohttp_server, nep):
    return await aiohttp_server(nep.app)


@pytest.fixture
def url(server):
    return str(server.make_url("")).rstrip("/")


@pytest.fixture
async def client(url):
    c = HAClient(url, TOKEN, timeout=3, min_wacht=0.05, max_wacht=0.2)
    await c.start()
    await c.wacht_op_verbinding(3)
    yield c
    await c.stop()


@pytest.fixture
def status(tmp_path):
    return Status.laad(str(tmp_path))


@pytest.fixture
def integraties():
    return laad_integraties()


async def wacht_tot(voorwaarde, timeout=3):
    for _ in range(int(timeout / 0.02)):
        if voorwaarde():
            return
        await asyncio.sleep(0.02)
    raise AssertionError("voorwaarde niet gehaald")
