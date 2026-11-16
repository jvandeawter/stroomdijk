"""Instellingen en het lokale statusbestand van Stroomdijk."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Instellingen:
    ha_url: str = "http://host.docker.internal:8124"
    geheim_dir: str = "/run/geheim"
    data_dir: str = "/data"
    poort: int = 8090

    @classmethod
    def uit_omgeving(cls, env: Optional[dict] = None) -> "Instellingen":
        env = os.environ if env is None else env
        d = cls()
        return cls(
            ha_url=env.get("STROOMDIJK_HA_URL", d.ha_url).rstrip("/"),
            geheim_dir=env.get("STROOMDIJK_GEHEIM", d.geheim_dir),
            data_dir=env.get("STROOMDIJK_DATA", d.data_dir),
            poort=int(env.get("STROOMDIJK_POORT", d.poort)),
        )

    @property
    def token_pad(self) -> str:
        return os.path.join(self.geheim_dir, "ha_token")

    def lees_token(self) -> Optional[str]:
        try:
            with open(self.token_pad) as f:
                return f.read().strip() or None
        except FileNotFoundError:
            return None


@dataclass
class Status:
    """Wat Stroomdijk zelf onthoudt. Staat in data_dir/status.json, nooit in git."""
    eigen_koppelingen: List[str] = field(default_factory=list)   # entry_id's die Stroomdijk maakte
    bronkeuze: Dict[str, str] = field(default_factory=dict)      # rol -> entity_id
    pad: Optional[str] = None

    @classmethod
    def laad(cls, data_dir: str) -> "Status":
        pad = os.path.join(data_dir, "status.json")
        try:
            with open(pad) as f:
                d = json.load(f)
        except FileNotFoundError:
            d = {}
        return cls(eigen_koppelingen=list(d.get("eigen_koppelingen", [])),
                   bronkeuze=dict(d.get("bronkeuze", {})), pad=pad)

    def bewaar(self) -> None:
        if not self.pad:
            raise ValueError("Status heeft geen pad")
        os.makedirs(os.path.dirname(self.pad), exist_ok=True)
        tmp = self.pad + ".tmp"
        with open(tmp, "w") as f:
            json.dump({"eigen_koppelingen": self.eigen_koppelingen, "bronkeuze": self.bronkeuze},
                      f, indent=2)
            f.write("\n")
        os.replace(tmp, self.pad)

    def koppeling_gemaakt(self, entry_id: str) -> None:
        if entry_id not in self.eigen_koppelingen:
            self.eigen_koppelingen.append(entry_id)
            self.bewaar()

    def koppeling_weg(self, entry_id: str) -> None:
        if entry_id in self.eigen_koppelingen:
            self.eigen_koppelingen.remove(entry_id)
            self.bewaar()
