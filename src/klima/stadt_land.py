"""Stadt oder Land? Einfluss städtischer Wärmeinseln auf Temperaturtrends (Meilenstein M7).

Stationen werden über ihre Entfernung zu Städten eingeteilt. Grundlage sind die „Populated
Places“ von Natural Earth (1:10 Mio.) mit der Einwohnerzahl des Ballungsraums (`POP_MAX`):

- **städtisch**: höchstens `radius_stadt_km` (Standard 10 km) vom Zentrum einer Stadt mit mindestens
  `einwohner_stadt` (Standard 100.000) Einwohnern,
- **ländlich**: mehr als `radius_land_km` (Standard 30 km) von jedem Ort mit mindestens
  `einwohner_land` (Standard 50.000) Einwohnern entfernt,
- sonst **Übergang** (wird in Vergleichen nicht verwendet).

Das ist bewusst einfach: Es kennt weder Stadtgrenzen noch Bebauung rund um die Station, und
Natural Earth enthält nicht jede Kleinstadt. Für einen ersten Vergleich genügt es.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

ERDRADIUS_KM = 6371.0


def staedte() -> pd.DataFrame:
    """Orte aus Natural Earth mit `name`, `land`, `breite`, `laenge`, `einwohner`."""
    import cartopy.io.shapereader as shpreader

    leser = shpreader.Reader(shpreader.natural_earth("10m", "cultural", "populated_places"))
    zeilen = [
        {
            "name": eintrag.attributes["NAME"],
            "land": eintrag.attributes.get("ADM0NAME"),
            "breite": float(eintrag.attributes["LATITUDE"]),
            "laenge": float(eintrag.attributes["LONGITUDE"]),
            "einwohner": float(eintrag.attributes["POP_MAX"]),
        }
        for eintrag in leser.records()
    ]
    return pd.DataFrame(zeilen)


def _einheitsvektoren(breite, laenge) -> np.ndarray:
    b, l_ = np.deg2rad(np.asarray(breite, float)), np.deg2rad(np.asarray(laenge, float))
    return np.column_stack([np.cos(b) * np.cos(l_), np.cos(b) * np.sin(l_), np.sin(b)])


def naechste_entfernung_km(
    stationen: pd.DataFrame, orte: pd.DataFrame
) -> tuple[np.ndarray, np.ndarray]:
    """Entfernung (km, Großkreis) jeder Station zum nächsten Ort und dessen Index in `orte`."""
    if orte.empty:
        return np.full(len(stationen), np.inf), np.full(len(stationen), -1)
    baum = cKDTree(_einheitsvektoren(orte["breite"], orte["laenge"]))
    sehne, index = baum.query(_einheitsvektoren(stationen["breite"], stationen["laenge"]))
    winkel = 2 * np.arcsin(np.clip(sehne / 2, 0, 1))
    return winkel * ERDRADIUS_KM, index


def klassifizieren(
    stationen: pd.DataFrame,
    orte: pd.DataFrame | None = None,
    einwohner_stadt: float = 100_000,
    radius_stadt_km: float = 10.0,
    einwohner_land: float = 50_000,
    radius_land_km: float = 30.0,
) -> pd.DataFrame:
    """Ergänzt `lage` (städtisch/ländlich/Übergang), `naechste_stadt` und `entfernung_km`."""
    orte = staedte() if orte is None else orte
    grossstaedte = orte[orte["einwohner"] >= einwohner_stadt].reset_index(drop=True)
    orte_land = orte[orte["einwohner"] >= einwohner_land].reset_index(drop=True)

    abstand_stadt, index = naechste_entfernung_km(stationen, grossstaedte)
    abstand_land, _ = naechste_entfernung_km(stationen, orte_land)
    lage = np.where(
        abstand_stadt <= radius_stadt_km,
        "städtisch",
        np.where(abstand_land > radius_land_km, "ländlich", "Übergang"),
    )
    namen = grossstaedte["name"].to_numpy()[np.clip(index, 0, None)] if len(grossstaedte) else None
    return stationen.assign(
        lage=pd.Categorical(lage, categories=["städtisch", "Übergang", "ländlich"]),
        naechste_stadt=namen,
        entfernung_km=np.round(abstand_stadt, 1),
    )
