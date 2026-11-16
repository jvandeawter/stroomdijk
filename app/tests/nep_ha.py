"""Een kleine nep-Home Assistant voor de tests: onboarding, WebSocket, flows en registries.

Gedraagt zich zoals de echte API voor zover Stroomdijk die gebruikt. Geen echte apparaten,
geen netwerk buiten de test.
"""
from __future__ import annotations

import itertools
import json
from typing import Dict, List, Optional

from aiohttp import WSMsgType, web

TOKEN = "nep-token"
LLAT = "nep-langlevend-token"


class NepHA:
    def __init__(self, onboarded: bool = True):
        self.onboarded = onboarded
        self.tokens = {TOKEN, LLAT} if onboarded else set()
        self.ids = itertools.count(1)
        self.entries: List[dict] = [{"entry_id": "e-mqtt", "domain": "mqtt", "title": "MQTT",
                                     "source": "user", "state": "loaded"}]
        self.flows: Dict[str, dict] = {}
        self.apparaten: List[dict] = []
        self.entiteiten: List[dict] = []
        self.states: Dict[str, dict] = {}
        self.ws: List[web.WebSocketResponse] = []
        self.abos: List[tuple] = []          # (ws, id, event_type)
        self.gebruiker: Optional[dict] = None
        self.http: dict = {"stable": {"server_port": 8123, "error": None},
                           "pending": {"server_port": 8124, "error": None},
                           "active_config_type": "pending", "revert_at": "2026-11-16T12:05:00+00:00"}

        self.app = web.Application()
        r = self.app.router
        r.add_get("/api/onboarding", self.onboarding)
        r.add_post("/api/onboarding/users", self.onboarding_users)
        r.add_post("/api/onboarding/{stap}", self.onboarding_stap)
        r.add_post("/auth/token", self.auth_token)
        r.add_get("/api/websocket", self.websocket)
        r.add_post("/api/config/config_entries/flow", self.flow_start)
        r.add_get("/api/config/config_entries/flow/{fid}", self.flow_get)
        r.add_post("/api/config/config_entries/flow/{fid}", self.flow_stap)
        r.add_delete("/api/config/config_entries/flow/{fid}", self.flow_weg)
        r.add_delete("/api/config/config_entries/entry/{eid}", self.entry_weg)

    # ---------- hulpjes voor tests ----------
    def ontdek(self, handler: str, source: str = "zeroconf", **placeholders) -> str:
        fid = f"f{next(self.ids)}"
        self.flows[fid] = {"flow_id": fid, "handler": handler, "step": "start",
                           "context": {"source": source, "title_placeholders": placeholders}}
        return fid

    async def zet(self, entity_id: str, state, **attrs) -> None:
        oud = self.states.get(entity_id)
        nieuw = {"entity_id": entity_id, "state": str(state),
                 "attributes": {**((oud or {}).get("attributes") or {}), **attrs},
                 "last_updated": "2026-11-16T12:00:00+00:00"}
        self.states[entity_id] = nieuw
        await self._event("state_changed", {"entity_id": entity_id, "old_state": oud, "new_state": nieuw})

    async def verbreek_alles(self) -> None:
        for ws in list(self.ws):
            await ws.close()

    def _auth(self, request) -> None:
        kop = request.headers.get("Authorization", "")
        if not kop.startswith("Bearer ") or kop[7:] not in self.tokens:
            raise web.HTTPUnauthorized()

    async def _event(self, soort: str, data: dict) -> None:
        for ws, mid, et in list(self.abos):
            if et == soort and not ws.closed:
                await ws.send_json({"id": mid, "type": "event", "event": {"event_type": soort, "data": data}})

    # ---------- onboarding ----------
    async def onboarding(self, request):
        klaar = self.gebruiker is not None or self.onboarded
        return web.json_response([{"step": s, "done": klaar} for s in
                                  ("user", "core_config", "analytics", "integration")])

    async def onboarding_users(self, request):
        if self.gebruiker or self.onboarded:
            return web.json_response({"message": "User step already done"}, status=403)
        self.gebruiker = await request.json()
        return web.json_response({"auth_code": "code-1"})

    async def auth_token(self, request):
        data = await request.post()
        if data.get("code") != "code-1":
            return web.json_response({"error": "invalid_request"}, status=400)
        self.tokens.add("toegang-1")
        return web.json_response({"access_token": "toegang-1", "token_type": "Bearer"})

    async def onboarding_stap(self, request):
        self._auth(request)
        return web.json_response({})

    # ---------- websocket ----------
    async def websocket(self, request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        await ws.send_json({"type": "auth_required"})
        m = await ws.receive_json()
        if m.get("access_token") not in self.tokens:
            await ws.send_json({"type": "auth_invalid", "message": "Invalid access token"})
            await ws.close()
            return ws
        await ws.send_json({"type": "auth_ok"})
        self.ws.append(ws)
        try:
            async for msg in ws:
                if msg.type != WSMsgType.TEXT:
                    continue
                m = json.loads(msg.data)
                await ws.send_json(self._antwoord(ws, m))
        finally:
            self.ws.remove(ws)
            self.abos = [a for a in self.abos if a[0] is not ws]
        return ws

    def _antwoord(self, ws, m: dict) -> dict:
        mid, soort = m["id"], m["type"]
        ok = lambda res: {"id": mid, "type": "result", "success": True, "result": res}  # noqa: E731
        if soort == "config_entries/get":
            return ok(self.entries)
        if soort == "config_entries/flow/progress":
            return ok([{k: f[k] for k in ("flow_id", "handler", "context")} for f in self.flows.values()])
        if soort == "config/device_registry/list":
            return ok(self.apparaten)
        if soort == "config/entity_registry/list":
            return ok(self.entiteiten)
        if soort == "get_states":
            return ok(list(self.states.values()))
        if soort == "subscribe_events":
            self.abos.append((ws, mid, m.get("event_type")))
            return ok(None)
        if soort == "http/config":
            return ok(self.http)
        if soort == "http/config/promote":
            if not self.http.get("pending"):
                return {"id": mid, "type": "result", "success": False,
                        "error": {"code": "not_allowed", "message": "No pending HTTP config to promote"}}
            self.http = {**self.http, "stable": self.http["pending"], "pending": None,
                         "active_config_type": "stable", "revert_at": None}
            return ok(None)
        if soort == "auth/long_lived_access_token":
            self.tokens.add(LLAT)
            return ok(LLAT)
        return {"id": mid, "type": "result", "success": False,
                "error": {"code": "unknown_command", "message": "Unknown command."}}

    # ---------- flows ----------
    FORMS = {
        "enphase_envoy": [{"name": "host", "required": True, "type": "string"},
                          {"name": "username", "type": "string"},
                          {"name": "password", "type": "string"}],
        "solaredge": [{"name": "site_id", "required": True, "selector": {"text": {}}},
                      {"name": "api_key", "required": True, "selector": {"text": {"type": "password"}}}],
        "homewizard": [],
    }

    def _form(self, f: dict, errors: Optional[dict] = None) -> dict:
        return {"type": "form", "flow_id": f["flow_id"], "handler": f["handler"], "step_id": "user",
                "data_schema": self.FORMS[f["handler"]], "errors": errors or {},
                "description_placeholders": None}

    async def flow_start(self, request):
        self._auth(request)
        body = await request.json()
        if body["handler"] not in self.FORMS:
            return web.json_response({"message": "Invalid handler specified"}, status=404)
        fid = self.ontdek(body["handler"], source="user")
        return web.json_response(self._form(self.flows[fid]))

    async def flow_get(self, request):
        self._auth(request)
        f = self.flows.get(request.match_info["fid"])
        if not f:
            return web.json_response({"message": "Flow not found"}, status=404)
        return web.json_response(self._form(f))

    async def flow_weg(self, request):
        self._auth(request)
        self.flows.pop(request.match_info["fid"], None)
        return web.json_response({})

    async def flow_stap(self, request):
        self._auth(request)
        f = self.flows.get(request.match_info["fid"])
        if not f:
            return web.json_response({"message": "Flow not found"}, status=404)
        invoer = await request.json()
        if invoer.get("password") == "fout" or invoer.get("api_key") == "fout":
            return web.json_response(self._form(f, {"base": "invalid_auth"}))
        del self.flows[f["flow_id"]]
        entry_id = f"e{next(self.ids)}"
        self.entries.append({"entry_id": entry_id, "domain": f["handler"], "title": f["handler"],
                             "source": f["context"]["source"], "state": "loaded"})
        await self._maak_apparaat(f["handler"], entry_id)
        return web.json_response({"type": "create_entry", "flow_id": f["flow_id"], "handler": f["handler"],
                                  "title": f["handler"], "result": {"entry_id": entry_id}})

    async def entry_weg(self, request):
        self._auth(request)
        eid = request.match_info["eid"]
        if not any(e["entry_id"] == eid for e in self.entries):
            return web.json_response({"message": "Entry not found"}, status=404)
        self.entries = [e for e in self.entries if e["entry_id"] != eid]
        weg = {x["entity_id"] for x in self.entiteiten if x["config_entry_id"] == eid}
        self.entiteiten = [x for x in self.entiteiten if x["config_entry_id"] != eid]
        for e in weg:
            self.states.pop(e, None)
        await self._event("entity_registry_updated", {"action": "remove"})
        return web.json_response({"require_restart": False})

    # ---------- apparaten die bij een koppeling horen ----------
    def ent(self, entry_id, dev, entity_id, platform, tk=None, uid=None):
        self.entiteiten.append({"entity_id": entity_id, "platform": platform, "config_entry_id": entry_id,
                                "device_id": dev, "translation_key": tk, "unique_id": uid or entity_id,
                                "disabled_by": None})

    async def _maak_apparaat(self, handler: str, entry_id: str) -> None:
        dev = f"d{next(self.ids)}"
        if handler == "enphase_envoy":
            self.apparaten.append({"id": dev, "name": "Envoy 1234", "name_by_user": None})
            self.ent(entry_id, dev, "sensor.envoy_1234_huidige_opwek", handler, "current_power_production")
            self.ent(entry_id, dev, "sensor.envoy_1234_opwek_vandaag", handler, "daily_production")
            self.ent(entry_id, dev, "sensor.omvormer_1", handler, None, "1234_inverter_1")
            self.states["sensor.envoy_1234_huidige_opwek"] = st("sensor.envoy_1234_huidige_opwek", "1.234", "kW", "power")
            self.states["sensor.envoy_1234_opwek_vandaag"] = st("sensor.envoy_1234_opwek_vandaag", "5600", "Wh", "energy")
            self.states["sensor.omvormer_1"] = st("sensor.omvormer_1", "310", "W", "power")
        elif handler == "solaredge":
            self.apparaten.append({"id": dev, "name": "SolarEdge", "name_by_user": None})
            self.ent(entry_id, dev, "sensor.solaredge_huidig_vermogen", handler, "current_power")
            self.states["sensor.solaredge_huidig_vermogen"] = st("sensor.solaredge_huidig_vermogen", "770", "W", "power")
        elif handler == "homewizard":
            self.apparaten.append({"id": dev, "name": "P1-meter", "name_by_user": None})
            self.ent(entry_id, dev, "sensor.p1_vermogen", handler, "active_power_w")
            self.states["sensor.p1_vermogen"] = st("sensor.p1_vermogen", "-500", "W", "power")
            for i, w in ((1, -300), (2, -100), (3, -100)):
                self.ent(entry_id, dev, f"sensor.p1_vermogen_fase_{i}", handler, "active_power_phase_w",
                         f"abc_active_power_l{i}_w")
                self.states[f"sensor.p1_vermogen_fase_{i}"] = st(f"sensor.p1_vermogen_fase_{i}", w, "W", "power")
                self.ent(entry_id, dev, f"sensor.p1_spanning_fase_{i}", handler, "active_voltage_phase_v",
                         f"abc_active_voltage_l{i}_v")
                self.states[f"sensor.p1_spanning_fase_{i}"] = st(f"sensor.p1_spanning_fase_{i}", 230.1, "V", "voltage")
        await self._event("entity_registry_updated", {"action": "create"})


def st(entity_id, state, unit, device_class):
    return {"entity_id": entity_id, "state": str(state), "last_updated": "2026-11-16T12:00:00+00:00",
            "attributes": {"unit_of_measurement": unit, "device_class": device_class}}
