"""NetworkManager via D-Bus: wifi scannen, hotspot aan en uit, verbinden met een wifi.

Alle verbindingen die Stroomdijk maakt heten 'stroomdijk-...', zodat we ze later precies
zo weer kunnen opruimen. Andere verbindingen (zoals de kabel) raken we nooit aan.
Het wifi-wachtwoord gaat alleen naar NetworkManager en komt nooit in een log.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

NM = "org.freedesktop.NetworkManager"
NM_PAD = "/org/freedesktop/NetworkManager"
NM_INSTELLINGEN = "/org/freedesktop/NetworkManager/Settings"
VOORVOEGSEL = "stroomdijk-"
HOTSPOT_ID = VOORVOEGSEL + "hotspot"
NM_STATE_CONNECTED_GLOBAL = 70
DEVICE_ACTIVATED = 100
DEVICE_FAILED = 120


def ontdubbel(netwerken: List[dict], eigen_ssid: str = "") -> List[dict]:
    """Eén regel per SSID (de sterkste), zonder lege namen en zonder onze eigen hotspot."""
    beste: Dict[str, dict] = {}
    for n in netwerken:
        ssid = n.get("ssid") or ""
        if not ssid or ssid == eigen_ssid:
            continue
        if ssid not in beste or n["sterkte"] > beste[ssid]["sterkte"]:
            beste[ssid] = n
    return sorted(beste.values(), key=lambda n: -n["sterkte"])


class NetworkManager:
    def __init__(self, ifname: str = "wlan0"):
        self.ifname = ifname
        self.bus = None
        self.nm = None
        self.dev_pad: Optional[str] = None
        self._hotspot_actief: Optional[str] = None

    async def _iface(self, pad: str, naam: str):
        intro = await self.bus.introspect(NM, pad)
        return self.bus.get_proxy_object(NM, pad, intro).get_interface(naam)

    async def open(self) -> None:
        from dbus_fast import BusType
        from dbus_fast.aio import MessageBus
        self.bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
        self.nm = await self._iface(NM_PAD, NM)
        self.dev_pad = await self.nm.call_get_device_by_ip_iface(self.ifname)

    async def wifi_aan(self) -> bool:
        return bool(await self.nm.get_wireless_enabled())

    async def heeft_netwerk(self) -> bool:
        return int(await self.nm.get_state()) >= NM_STATE_CONNECTED_GLOBAL

    async def hw_adres(self) -> str:
        dev = await self._iface(self.dev_pad, NM + ".Device")
        return str(await dev.get_hw_address())

    async def scan(self) -> List[dict]:
        from dbus_fast.errors import DBusError
        w = await self._iface(self.dev_pad, NM + ".Device.Wireless")
        try:
            await w.call_request_scan({})
        except DBusError as e:          # bijvoorbeeld: net nog gescand
            log.info("scan niet gestart: %s", e)
        await asyncio.sleep(4)
        uit = []
        for ap_pad in await w.call_get_all_access_points():
            try:
                ap = await self._iface(ap_pad, NM + ".AccessPoint")
                ssid = bytes(await ap.get_ssid()).decode("utf-8", "replace")
                beveiligd = bool((await ap.get_flags()) & 1 or await ap.get_wpa_flags() or await ap.get_rsn_flags())
                uit.append({"ssid": ssid, "sterkte": int(await ap.get_strength()), "beveiligd": beveiligd})
            except DBusError:
                continue                 # access point net verdwenen
        return uit

    async def _activeer(self, instellingen: dict) -> Tuple[str, str]:
        return await self.nm.call_add_and_activate_connection(instellingen, self.dev_pad, "/")

    async def start_hotspot(self, ssid: str) -> None:
        from dbus_fast import Variant
        await self.vergeet(alleen=HOTSPOT_ID)
        instellingen = {
            "connection": {"id": Variant("s", HOTSPOT_ID), "type": Variant("s", "802-11-wireless"),
                           "autoconnect": Variant("b", False)},
            "802-11-wireless": {"ssid": Variant("ay", ssid.encode()), "mode": Variant("s", "ap"),
                                "band": Variant("s", "bg")},
            "ipv4": {"method": Variant("s", "shared")},
            "ipv6": {"method": Variant("s", "ignore")},
        }
        _, actief = await self._activeer(instellingen)
        self._hotspot_actief = actief
        log.info("hotspot %s gestart", ssid)

    async def stop_hotspot(self) -> None:
        await self.vergeet(alleen=HOTSPOT_ID)
        self._hotspot_actief = None

    async def verbind(self, ssid: str, wachtwoord: str, timeout: float = 40) -> Tuple[bool, str]:
        from dbus_fast import Variant
        from dbus_fast.errors import DBusError
        naam = VOORVOEGSEL + "wifi"
        await self.vergeet(alleen=naam)
        instellingen = {
            "connection": {"id": Variant("s", naam), "type": Variant("s", "802-11-wireless"),
                           "autoconnect": Variant("b", True)},
            "802-11-wireless": {"ssid": Variant("ay", ssid.encode()), "mode": Variant("s", "infrastructure")},
            "ipv4": {"method": Variant("s", "auto")},
            "ipv6": {"method": Variant("s", "auto")},
        }
        if wachtwoord:
            instellingen["802-11-wireless-security"] = {"key-mgmt": Variant("s", "wpa-psk"),
                                                        "psk": Variant("s", wachtwoord)}
        try:
            await self._activeer(instellingen)
        except DBusError as e:
            return False, f"NetworkManager weigerde de verbinding ({e.type})"
        dev = await self._iface(self.dev_pad, NM + ".Device")
        for _ in range(int(timeout * 2)):
            staat = int(await dev.get_state())
            if staat == DEVICE_ACTIVATED:
                return True, ""
            if staat == DEVICE_FAILED:
                break
            await asyncio.sleep(0.5)
        await self.vergeet(alleen=naam)
        return False, "Verbinden lukte niet. Klopt het wachtwoord, en is het netwerk in de buurt?"

    async def vergeet(self, alleen: Optional[str] = None) -> List[str]:
        """Verwijdert verbindingen van Stroomdijk (of alleen die ene). Raakt andere nooit aan."""
        inst = await self._iface(NM_INSTELLINGEN, NM + ".Settings")
        weg = []
        for pad in await inst.call_list_connections():
            con = await self._iface(pad, NM + ".Settings.Connection")
            cid = (await con.call_get_settings())["connection"]["id"].value
            if (alleen and cid == alleen) or (not alleen and cid.startswith(VOORVOEGSEL)):
                await con.call_delete()
                weg.append(cid)
        return weg
