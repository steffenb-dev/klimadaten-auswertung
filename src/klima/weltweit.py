"""Globale Landtemperatur aus GHCN-Monthly v4 (Meilenstein M4).

Verfahren (SPEC.md, Abschnitt 3.1):
1. Monatliche Anomalien je Station gegenüber der Referenzperiode (Standard 1951–1980).
2. Gitterung auf 5°×5°-Zellen: Mittel der Stationsanomalien je Zelle und Monat.
3. Flächengewichtetes Mittel über alle besetzten Zellen (Gewicht = cos(Breite)).

Gemittelt wird nur über **besetzte** Zellen – es wird nicht in Lücken interpoliert. Die
Nordhalbkugel hat deutlich mehr Landfläche und Stationen; das globale Mittel ist deshalb
nordlastig. Wie bei CRUTEM wird zusätzlich das Mittel der beiden Halbkugeln berechnet.

Hinweis zum Vergleich mit NASA GISTEMP „nur Land“ (`GLB.Ts`): GISTEMP überträgt
Stationsanomalien bis 1.200 km weit, also auch auf Ozeanflächen nahe der Küsten und in
schlecht abgedeckte Polarregionen. Kleine Unterschiede zu unserer einfacheren Methode sind
deshalb zu erwarten.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from klima import einlesen
from klima.anomalien import anomalien, jahreswerte, standard_referenzperiode
from klima.gitter import flaechenmittel, gitter_mittel
from klima.konfiguration import lade_analyse
from klima.trend import steigung_je_gruppe

GEBIETE = {
    "global": None,
    "nordhalbkugel": (0.0, 90.0),
    "suedhalbkugel": (-90.0, 0.0),
}


def standard_zellgroesse() -> float:
    return float(lade_analyse()["gitter"]["zellgroesse_grad"])


def stationsanomalien(
    variante: str = "qcf",
    referenz: tuple[int, int] | None = None,
    mindestjahre: int | None = None,
) -> pd.DataFrame:
    """Monatliche Anomalien aller GHCNm-Stationen mit ausreichender Referenz, inkl. Koordinaten."""
    werte = einlesen.ghcnm_monatswerte(variante, spalten=["stations_id", "jahr", "monat", "tavg"])
    ergebnis = anomalien(werte, "tavg", referenz=referenz, mindestjahre=mindestjahre)
    stationen = einlesen.ghcnm_stationen(variante)[["stations_id", "breite", "laenge"]]
    ergebnis["stations_id"] = ergebnis["stations_id"].astype(str)
    ergebnis = ergebnis.merge(stationen.astype({"stations_id": str}), on="stations_id")
    return ergebnis[["stations_id", "jahr", "monat", "breite", "laenge", "anomalie"]]


def gitteranomalien(
    variante: str = "qcf",
    referenz: tuple[int, int] | None = None,
    groesse: float | None = None,
) -> pd.DataFrame:
    """Monatliche Anomalie je Gitterzelle: `jahr`, `monat`, `zelle_breite`, `zelle_laenge`,
    `anomalie`, `stationen`."""
    groesse = groesse or standard_zellgroesse()
    return gitter_mittel(stationsanomalien(variante, referenz), groesse=groesse)


def gebietsmittel(gitter: pd.DataFrame, gebiet: str = "global") -> pd.DataFrame:
    """Flächengewichtetes Monatsmittel für `global`, `nordhalbkugel` oder `suedhalbkugel`."""
    grenzen = GEBIETE[gebiet]
    if grenzen is not None:
        gitter = gitter[
            (gitter["zelle_breite"] > grenzen[0]) & (gitter["zelle_breite"] < grenzen[1])
        ]
    return flaechenmittel(gitter)


def jahresanomalien(
    gitter: pd.DataFrame, mindestmonate: int = 12, gebiete: tuple[str, ...] = tuple(GEBIETE)
) -> pd.DataFrame:
    """Jahresmittel je Gebiet (Spalten) plus `halbkugelmittel` = (Nord + Süd) / 2."""
    reihen = {}
    for gebiet in gebiete:
        monatlich = gebietsmittel(gitter, gebiet)
        jahre = jahreswerte(monatlich, "anomalie", gruppe=None, mindestmonate=mindestmonate)
        reihen[gebiet] = jahre.set_index("jahr")["anomalie"]
    tabelle = pd.DataFrame(reihen).sort_index().rename_axis("jahr")
    if {"nordhalbkugel", "suedhalbkugel"} <= set(tabelle.columns):
        tabelle["halbkugelmittel"] = (tabelle["nordhalbkugel"] + tabelle["suedhalbkugel"]) / 2
    return tabelle


def abdeckung(
    gitter: pd.DataFrame, stationsanomalien_: pd.DataFrame, groesse: float | None = None
) -> pd.DataFrame:
    """Je Jahr: aktive Stationen, besetzte Zellen und Anteil der Erdoberfläche dieser Zellen.

    Eine Station bzw. Zelle zählt als aktiv, wenn sie im Jahr mindestens einen Monatswert hat.
    """
    stationen = stationsanomalien_.groupby("jahr")["stations_id"].nunique()
    zellen = gitter.drop_duplicates(["jahr", "zelle_breite", "zelle_laenge"])
    groesse = groesse or standard_zellgroesse()
    # Fläche einer Zelle relativ zur Erdoberfläche: Breitenband × Längenanteil
    breite = np.deg2rad(zellen["zelle_breite"].to_numpy())
    halb = np.deg2rad(groesse / 2)
    flaeche = (np.sin(breite + halb) - np.sin(breite - halb)) / 2 * (groesse / 360)
    anteil = pd.Series(flaeche, index=zellen.index).groupby(zellen["jahr"]).sum() * 100
    return (
        pd.DataFrame(
            {
                "stationen": stationen,
                "zellen": zellen.groupby("jahr").size(),
                "flaechenanteil": anteil,
            }
        )
        .fillna(0)
        .astype({"stationen": int, "zellen": int})
        .rename_axis("jahr")
    )


def jahrzehntmittel(gitter: pd.DataFrame, mindestmonate: int = 60) -> pd.DataFrame:
    """Mittlere Anomalie je Gitterzelle und Jahrzehnt (`jahrzehnt` = 1880, 1890, …).

    Eine Zelle zählt in einem Jahrzehnt nur mit mindestens `mindestmonate` Monatswerten.
    """
    mit_jahrzehnt = gitter.assign(jahrzehnt=(gitter["jahr"] // 10) * 10)
    mittel = (
        mit_jahrzehnt.groupby(["jahrzehnt", "zelle_breite", "zelle_laenge"])["anomalie"]
        .agg(["mean", "count"])
        .reset_index()
    )
    mittel = mittel[mittel["count"] >= mindestmonate]
    return mittel.rename(columns={"mean": "anomalie", "count": "monate"})


def stationstrends(
    variante: str,
    von: int = 1951,
    bis: int | None = None,
    mindestanteil: float = 0.8,
) -> pd.DataFrame:
    """Trend (°C/Dekade) je GHCNm-Station aus Jahresmitteln der Temperatur.

    Nur Stationen mit mindestens `mindestanteil` vollständigen Jahren im Zeitraum.
    Vektorisiert (ohne Schleife über ~28.000 Stationen): Steigung = Kov(x, y) / Var(x).
    """
    werte = einlesen.ghcnm_monatswerte(
        variante, von=von, bis=bis, spalten=["stations_id", "jahr", "monat", "tavg"]
    )
    bis = bis or int(werte["jahr"].max())
    jahre = jahreswerte(werte, "tavg")
    jahre["stations_id"] = jahre["stations_id"].astype(str)

    anzahl = jahre.groupby("stations_id")["jahr"].transform("count")
    jahre = jahre[anzahl >= mindestanteil * (bis - von + 1)]
    steigung = steigung_je_gruppe(jahre, "stations_id", "jahr", "tavg")
    gruppen = jahre.groupby("stations_id")
    trends = (steigung * 10).rename("trend").reset_index()
    trends["jahre"] = trends["stations_id"].map(gruppen.size())
    stationen = einlesen.ghcnm_stationen(variante).astype({"stations_id": str})
    return stationen.merge(trends, on="stations_id")


def homogenisierungseffekt(von: int = 1951, bis: int | None = None) -> pd.DataFrame:
    """Trend je Station in QCU und QCF sowie die Differenz `qcf - qcu` (°C/Dekade)."""
    qcu = stationstrends("qcu", von, bis)[["stations_id", "trend"]]
    qcf = stationstrends("qcf", von, bis)
    vergleich = qcf.rename(columns={"trend": "trend_qcf"}).merge(
        qcu.rename(columns={"trend": "trend_qcu"}), on="stations_id"
    )
    vergleich["differenz"] = vergleich["trend_qcf"] - vergleich["trend_qcu"]
    return vergleich


def referenzperiode_text(referenz: tuple[int, int] | None = None) -> str:
    von, bis = referenz or standard_referenzperiode()
    return f"{von}–{bis}"
