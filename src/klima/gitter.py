"""Gitterung und Flächengewichtung (SPEC.md, Abschnitt 3.1, Schritte 3 und 6).

Stationen sind sehr ungleich verteilt. Damit dicht besetzte Regionen das Ergebnis nicht
dominieren, werden Stationsanomalien zuerst je Gitterzelle gemittelt. Die Zellen werden
dann mit dem Kosinus ihrer mittleren Breite gewichtet, weil Zellen gleicher Gradgröße zu
den Polen hin kleiner werden.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def zellmitte(koordinate: pd.Series | np.ndarray, groesse: float, minimum: float) -> np.ndarray:
    """Mitte der Gitterzelle, in die eine Koordinate fällt (Zellen beginnen bei `minimum`)."""
    index = np.floor((np.asarray(koordinate, dtype=np.float64) - minimum) / groesse)
    return minimum + (index + 0.5) * groesse


def gitter_mittel(
    werte: pd.DataFrame,
    wert: str = "anomalie",
    groesse: float = 5.0,
    zeit: tuple[str, ...] = ("jahr", "monat"),
) -> pd.DataFrame:
    """Mittelt Stationswerte je Gitterzelle und Zeitschritt.

    Erwartet die Spalten `breite`, `laenge`, die Zeitspalten und `wert`. Ergebnis:
    Zeitspalten, `zelle_breite`, `zelle_laenge` (Zellmitte), `wert`, `stationen`.
    """
    zeit = tuple(z for z in zeit if z in werte)
    mit_zelle = werte.assign(
        zelle_breite=zellmitte(werte["breite"], groesse, -90.0),
        zelle_laenge=zellmitte(werte["laenge"], groesse, -180.0),
    )
    ergebnis = (
        mit_zelle.dropna(subset=[wert])
        .groupby([*zeit, "zelle_breite", "zelle_laenge"], observed=True)[wert]
        .agg(["mean", "count"])
        .reset_index()
    )
    return ergebnis.rename(columns={"mean": wert, "count": "stationen"})


def flaechenmittel(
    gitter: pd.DataFrame,
    wert: str = "anomalie",
    zeit: tuple[str, ...] = ("jahr", "monat"),
) -> pd.DataFrame:
    """Flächengewichtetes Mittel über alle besetzten Zellen je Zeitschritt.

    Ergebnis: Zeitspalten, `wert`, `zellen` (Anzahl besetzter Zellen).
    """
    zeit = tuple(z for z in zeit if z in gitter)
    gewicht = np.cos(np.deg2rad(gitter["zelle_breite"]))
    hilfs = gitter.assign(_gewicht=gewicht, _produkt=gitter[wert] * gewicht)
    summen = hilfs.groupby(list(zeit), observed=True).agg(
        _produkt=("_produkt", "sum"), _gewicht=("_gewicht", "sum"), zellen=(wert, "count")
    )
    summen[wert] = summen["_produkt"] / summen["_gewicht"]
    return summen[[wert, "zellen"]].reset_index()


def regionalmittel(
    werte: pd.DataFrame,
    stationen: pd.DataFrame,
    wert: str = "anomalie",
    groesse: float = 5.0,
    zeit: tuple[str, ...] = ("jahr", "monat"),
) -> pd.DataFrame:
    """Gitterung + Flächengewichtung für Stationswerte; Koordinaten kommen aus `stationen`."""
    koordinaten = stationen[["stations_id", "breite", "laenge"]].astype({"stations_id": str})
    mit_ort = werte.astype({"stations_id": str}).merge(koordinaten, on="stations_id")
    return flaechenmittel(gitter_mittel(mit_ort, wert, groesse, zeit), wert, zeit)
