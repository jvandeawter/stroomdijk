"""Verbinding met Home Assistant via de officiële WebSocket- en REST-API.

Eén blijvende WebSocket-verbinding. Valt die weg, dan verbindt de client opnieuw met
oplopende wachttijd en zet hij de abonnementen opnieuw op. Het token komt nooit in
een foutmelding of log.
"""
from __future__ import annotations

import asyncio
import inspect
import logging
from typing import Any, Callable, Dict, Optional, Tuple

import aiohttp

log = logging.getLogger(__name__)


class HAFout(Exception):
    """Home Assistant gaf een fout of is niet bereikbaar."""


class AuthFout(HAFout):
    """Home Assistant weigert het token."""


class HAClient:
    def __init__(self, url: str, token: str, session: Optional[aiohttp.ClientSession] = None,
                 timeout: float = 15, min_wacht: float = 1, max_wacht: float = 60):
        self.url = url.rstrip("/")
        self._token = token
        self._session = session
        self._eigen_session = session is None
        self.timeout = timeout
        self.min_wacht = min_wacht
        self.max_wacht = max_wacht

        self._ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self._id = 0
        self._wacht: Dict[int, asyncio.Future] = {}
        self._abos: Dict[int, Callable] = {}
        self._specs: Dict[str, Tuple[dict, Callable]] = {}
        self._taak: Optional[asyncio.Task] = None
        self._klaar: Optional[asyncio.Event] = None
        self._gestopt = False

        self.verbonden = False
        self.fout: Optional[str] = None
        self.bij_verbinden: list = []   # async functies die na elke (her)verbinding draaien

    # ---------- levensloop ----------
    async def start(self) -> None:
        self._klaar = asyncio.Event()
        if self._session is None:
            self._session = aiohttp.ClientSession()
        self._gestopt = False
        self._taak = asyncio.ensure_future(self._lus())

    async def wacht_op_verbinding(self, timeout: Optional[float] = None) -> None:
        assert self._klaar is not None, "eerst start() aanroepen"
        await asyncio.wait_for(self._klaar.wait(), timeout)

    async def stop(self) -> None:
        self._gestopt = True
        if self._ws is not None:
            await self._ws.close()
        if self._taak is not None:
            self._taak.cancel()
            try:
                await self._taak
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        if self._eigen_session and self._session is not None:
            await self._session.close()

    async def _lus(self) -> None:
        wacht = self.min_wacht
        while not self._gestopt:
            gelukt = False
            try:
                await self._verbind()
                gelukt = True
                lezer = asyncio.ensure_future(self._lees())
                try:
                    for sleutel, (bericht, cb) in list(self._specs.items()):
                        await self._stuur(bericht, abo=cb)
                    for f in self.bij_verbinden:
                        await f()
                    assert self._klaar is not None
                    self._klaar.set()
                    log.info("verbonden met Home Assistant")
                    await lezer
                finally:
                    lezer.cancel()
            except asyncio.CancelledError:
                raise
            except AuthFout as e:
                self.fout = f"token geweigerd: {e}"
                log.warning(self.fout)
                wacht = self.max_wacht
            except (aiohttp.ClientError, OSError, asyncio.TimeoutError, HAFout, ValueError) as e:
                self.fout = f"{type(e).__name__}: {e}"
                log.warning("Home Assistant niet bereikbaar: %s", self.fout)
            finally:
                self._verbroken()
            if self._gestopt:
                break
            if gelukt:
                wacht = self.min_wacht
            await asyncio.sleep(wacht)
            if not gelukt:
                wacht = min(wacht * 2, self.max_wacht)

    async def _verbind(self) -> None:
        assert self._session is not None
        ws = await self._session.ws_connect(f"{self.url}/api/websocket", heartbeat=30)
        try:
            m = await ws.receive_json(timeout=self.timeout)
            if m.get("type") != "auth_required":
                raise HAFout(f"onverwacht bericht: {m.get('type')}")
            await ws.send_json({"type": "auth", "access_token": self._token})
            m = await ws.receive_json(timeout=self.timeout)
            if m.get("type") == "auth_invalid":
                raise AuthFout(m.get("message", "ongeldig"))
            if m.get("type") != "auth_ok":
                raise HAFout(f"onverwacht bericht: {m.get('type')}")
        except BaseException:
            await ws.close()
            raise
        self._ws = ws
        self._id = 0
        self.verbonden = True
        self.fout = None

    def _verbroken(self) -> None:
        self.verbonden = False
        if self._klaar is not None:
            self._klaar.clear()
        for fut in self._wacht.values():
            if not fut.done():
                fut.set_exception(HAFout("verbinding met Home Assistant verbroken"))
        self._wacht.clear()
        self._abos.clear()
        self._ws = None

    async def _lees(self) -> None:
        assert self._ws is not None
        async for msg in self._ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                data = msg.json()
                for m in data if isinstance(data, list) else [data]:
                    self._verwerk(m)
            elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                break

    def _verwerk(self, m: dict) -> None:
        soort = m.get("type")
        if soort == "result":
            fut = self._wacht.pop(m.get("id"), None)
            if fut is not None and not fut.done():
                fut.set_result(m)
        elif soort == "event":
            cb = self._abos.get(m.get("id"))
            if cb is None:
                return
            try:
                r = cb(m.get("event"))
                if inspect.isawaitable(r):
                    asyncio.ensure_future(r)
            except Exception:  # noqa: BLE001
                log.exception("fout in afhandeling van event")

    # ---------- berichten ----------
    async def _stuur(self, bericht: dict, abo: Optional[Callable] = None) -> Any:
        if self._ws is None:
            raise HAFout("niet verbonden met Home Assistant")
        self._id += 1
        mid = self._id
        fut = asyncio.get_running_loop().create_future()
        self._wacht[mid] = fut
        if abo is not None:
            self._abos[mid] = abo
        await self._ws.send_json({"id": mid, **bericht})
        try:
            m = await asyncio.wait_for(fut, self.timeout)
        except asyncio.TimeoutError:
            self._wacht.pop(mid, None)
            self._abos.pop(mid, None)
            raise HAFout(f"geen antwoord op {bericht.get('type')}")
        if not m.get("success"):
            self._abos.pop(mid, None)
            fout = m.get("error") or {}
            raise HAFout(f"{bericht.get('type')}: {fout.get('code')}: {fout.get('message')}")
        return m.get("result")

    async def vraag(self, soort: str, **data: Any) -> Any:
        """Stuurt één WebSocket-opdracht en geeft het resultaat terug."""
        return await self._stuur({"type": soort, **data})

    async def abonneer(self, sleutel: str, bericht: dict, callback: Callable) -> None:
        """Abonnement dat na elke herverbinding vanzelf opnieuw wordt opgezet."""
        self._specs[sleutel] = (bericht, callback)
        if self.verbonden:
            await self._stuur(bericht, abo=callback)

    # ---------- REST ----------
    async def rest(self, methode: str, pad: str, json: Optional[dict] = None) -> Any:
        assert self._session is not None, "eerst start() aanroepen"
        kop = {"Authorization": f"Bearer {self._token}"}
        async with self._session.request(methode, self.url + pad, headers=kop, json=json,
                                         timeout=aiohttp.ClientTimeout(total=self.timeout)) as r:
            tekst = await r.text()
            if r.status == 401:
                raise AuthFout("token geweigerd")
            if r.status >= 400:
                raise HAFout(f"{methode} {pad}: {r.status}: {tekst[:200]}")
            if not tekst:
                return None
            import json as _json
            return _json.loads(tekst)
