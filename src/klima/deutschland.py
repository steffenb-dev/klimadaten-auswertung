"""Auswertungen für Deutschland (Meilenstein M3).

Vergleicht eigene Gebietsmittel – berechnet aus Stationsdaten mit Anomalien, Gitterung und
Flächengewichtung – mit den offiziellen Gebietsmitteln des DWD. Der DWD interpoliert dafür
auf ein 1-km-Raster; unsere einfachere Methode sollte trotzdem sehr nahe herankommen.
"""

from __future__ import annotations

import pandas as pd

from klima import einlesen
from klima.anomalien import anomalien, jahreswerte, standard_referenzperiode
from klima.gitter import regionalmittel
from klima.konfiguration import lade_analyse
from klima.trend import linearer_trend

GEBIET = "Deutschland"
GHCNM_LAND = "GM"

# Namen der Reihen, wie sie in Tabellen und Legenden erscheinen
DWD_OFFIZIELL = "DWD-Gebietsmittel (offiziell)"
DWD_STATIONEN = "DWD-Stationen (eigene Berechnung)"
GHCNM_QCF = "GHCNm homogenisiert (eigene Berechnung)"
GHCNM_QCU = "GHCNm unbereinigt (eigene Berechnung)"


def standard_zellgroesse() -> float:
    return float(lade_analyse()["gitter"]["zellgroesse_regional_grad"])


def _reihe(tabelle: pd.DataFrame, spalte: str = "anomalie") -> pd.Series:
    return tabelle.set_index("jahr")[spalte].astype("float64")


# --- Temperatur ---------------------------------------------------------------------


def _offizielle_temperatur(referenz: tuple[int, int]) -> pd.Series:
    monate = einlesen.dwd_gebietsmittel("temperatur", gebiete=[GEBIET])
    jahre = jahreswerte(monate, "temperatur", gruppe="gebiet")
    return _reihe(anomalien(jahre, "temperatur", gruppe="gebiet", referenz=referenz))


def _gebietsmittel_temperatur(
    werte: pd.DataFrame, stationen: pd.DataFrame, wert: str, referenz, groesse: float
) -> pd.Series:
    """Monatliche Stationsanomalien -> Gitter -> Flächenmittel -> Jahresmittel."""
    monatlich = anomalien(werte, wert, referenz=referenz)
    flaeche = regionalmittel(monatlich, stationen, groesse=groesse)
    return _reihe(jahreswerte(flaeche, "anomalie", gruppe=None))


def temperatur_jahresanomalien(
    referenz: tuple[int, int] | None = None, groesse: float | None = None
) -> pd.DataFrame:
    """Jahresmittel der Temperaturanomalie für Deutschland aus vier Quellen (Spalten).

    Index: Jahr. Anomalien in °C gegenüber der Referenzperiode.
    """
    referenz = referenz or standard_referenzperiode()
    groesse = groesse or standard_zellgroesse()

    dwd_stationen = einlesen.dwd_stationen("monat")
    dwd_werte = einlesen.dwd_monatswerte(spalten=["stations_id", "jahr", "monat", "tmittel"])
    ghcnm_stationen = einlesen.ghcnm_stationen("qcf", laender=[GHCNM_LAND])

    reihen = {
        DWD_OFFIZIELL: _offizielle_temperatur(referenz),
        DWD_STATIONEN: _gebietsmittel_temperatur(
            dwd_werte, dwd_stationen, "tmittel", referenz, groesse
        ),
    }
    for variante, name in (("qcf", GHCNM_QCF), ("qcu", GHCNM_QCU)):
        werte = einlesen.ghcnm_monatswerte(
            variante,
            stationen=ghcnm_stationen["stations_id"],
            spalten=["stations_id", "jahr", "monat", "tavg"],
        )
        reihen[name] = _gebietsmittel_temperatur(werte, ghcnm_stationen, "tavg", referenz, groesse)
    return pd.DataFrame(reihen).sort_index().rename_axis("jahr")


# --- Niederschlag ---------------------------------------------------------------------


def niederschlag_jahresanomalien(
    referenz: tuple[int, int] | None = None, groesse: float | None = None
) -> pd.DataFrame:
    """Relative Anomalie der Jahressumme des Niederschlags in % (Spalten: Quellen)."""
    referenz = referenz or standard_referenzperiode()
    groesse = groesse or standard_zellgroesse()

    monate = einlesen.dwd_gebietsmittel("niederschlag", gebiete=[GEBIET])
    jahre = jahreswerte(monate, "niederschlag", gruppe="gebiet", aggregation="summe")
    offiziell = anomalien(jahre, "niederschlag", gruppe="gebiet", referenz=referenz, relativ=True)

    werte = einlesen.dwd_monatswerte(spalten=["stations_id", "jahr", "monat", "niederschlag"])
    summen = jahreswerte(werte, "niederschlag", aggregation="summe")
    stationsanomalien = anomalien(summen, "niederschlag", referenz=referenz, relativ=True)
    eigene = regionalmittel(
        stationsanomalien, einlesen.dwd_stationen("monat"), groesse=groesse, zeit=("jahr",)
    )
    return (
        pd.DataFrame({DWD_OFFIZIELL: _reihe(offiziell), DWD_STATIONEN: _reihe(eigene)})
        .sort_index()
        .rename_axis("jahr")
    )


def niederschlag_jahressummen() -> pd.Series:
    """Offizielle Jahressumme des Niederschlags in Deutschland (mm)."""
    monate = einlesen.dwd_gebietsmittel("niederschlag", gebiete=[GEBIET])
    jahre = jahreswerte(monate, "niederschlag", gruppe="gebiet", aggregation="summe")
    return _reihe(jahre, "niederschlag")


# --- Stationen ---------------------------------------------------------------------------


def stationstrends(
    von: int = 1951,
    bis: int | None = None,
    mindestanteil: float = 0.8,
    wert: str = "tmittel",
) -> pd.DataFrame:
    """Linearer Trend je DWD-Station für Jahresmittel bzw. -summe im Zeitraum.

    Nur Stationen mit mindestens `mindestanteil` vollständigen Jahren im Zeitraum.
    Ergebnis: Stationsliste plus `trend` (Einheit/Dekade), `unsicherheit_95`, `jahre`.
    Niederschlag wird relativ angegeben: % des Stationsmittels im Zeitraum je Dekade.
    """
    werte = einlesen.dwd_monatswerte(
        spalten=["stations_id", "jahr", "monat", wert], von=von, bis=bis
    )
    bis = bis or int(werte["jahr"].max())
    aggregation = "summe" if wert == "niederschlag" else "mittel"
    jahre = jahreswerte(werte, wert, aggregation=aggregation)
    benoetigt = mindestanteil * (bis - von + 1)

    zeilen = []
    for stations_id, gruppe in jahre.groupby("stations_id", observed=True):
        if len(gruppe) < benoetigt:
            continue
        reihe = gruppe.set_index("jahr")[wert]
        if aggregation == "summe":
            reihe = reihe / reihe.mean() * 100
        trend = linearer_trend(reihe)
        zeilen.append(
            {
                "stations_id": str(stations_id),
                "trend": trend.steigung_pro_dekade,
                "unsicherheit_95": trend.unsicherheit_95,
                "jahre": trend.anzahl,
            }
        )
    trends = pd.DataFrame(zeilen)
    stationen = einlesen.dwd_stationen("monat").astype({"stations_id": str})
    return stationen.merge(trends, on="stations_id", how="inner")


def station_jahreswerte(stations_id: str, wert: str = "tmittel") -> pd.Series:
    """Jahresmittel (Temperatur) bzw. Jahressumme (Niederschlag) einer DWD-Station."""
    werte = einlesen.dwd_monatswerte(
        stationen=[stations_id], spalten=["stations_id", "jahr", "monat", wert]
    )
    if werte.empty:
        raise ValueError(f"Keine Monatswerte für DWD-Station {stations_id}.")
    aggregation = "summe" if wert == "niederschlag" else "mittel"
    return _reihe(jahreswerte(werte, wert, aggregation=aggregation), wert)


def station_suchen(name: str) -> pd.DataFrame:
    """DWD-Stationen, deren Name `name` enthält (ohne Groß-/Kleinschreibung)."""
    stationen = einlesen.dwd_stationen("monat")
    return stationen[stationen["name"].str.contains(name, case=False, regex=False)]


# --- Kenntage und Niederschlagsindizes ---------------------------------------------------


def indizes_gebietsmittel(
    stationsjahre: pd.DataFrame,
    spalten: list[str],
    referenz: tuple[int, int] | None = None,
    groesse: float | None = None,
    stationen: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Gebietsmittel Deutschland je Jahr für Indizes je Station und Jahr (Spalten = Indizes).

    Je Index: Abweichung jeder Station von ihrem Mittel der Referenzperiode → 1°-Gitter →
    Flächenmittel; dazu das ebenso gegitterte Referenzmittel addiert. So verzerren
    wechselnde Stationsnetze (z. B. zusätzliche Bergstationen) das Ergebnis kaum.
    """
    from klima.anomalien import klimatologie

    referenz = referenz or standard_referenzperiode()
    groesse = groesse or standard_zellgroesse()
    stationen = stationen if stationen is not None else einlesen.dwd_stationen("tag")
    reihen = {}
    for spalte in spalten:
        werte = stationsjahre[["stations_id", "jahr", spalte]].dropna()
        abweichung = anomalien(werte, spalte, referenz=referenz)
        flaeche = regionalmittel(abweichung, stationen, groesse=groesse, zeit=("jahr",))
        klima = klimatologie(werte, spalte, referenz=referenz).rename(
            columns={"referenzmittel": "klima"}
        )
        klima_de = regionalmittel(
            klima.assign(jahr=0), stationen, wert="klima", groesse=groesse, zeit=("jahr",)
        )["klima"].iloc[0]
        reihen[spalte] = flaeche.set_index("jahr")["anomalie"] + klima_de
    return pd.DataFrame(reihen).sort_index().rename_axis("jahr")
