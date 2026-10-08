"""Tagesgang aus DWD-Stundenwerten: Welche Uhrzeiten erwärmen sich am stärksten, und wie groß
ist die städtische Wärmeinsel im Tagesverlauf? (Meilenstein M7)

Alle Uhrzeiten in **MEZ** (UTC + 1 Stunde, ohne Sommerzeit) – das entspricht in Deutschland
ungefähr der Sonnenzeit. Die Stundenwerte liegen nach dem Einlesen einheitlich in UTC vor
(Parser `dwd.lies_stundenwerte_station` rechnet MEZ-Zeiträume laut Metadaten um).
"""

from __future__ import annotations

import pandas as pd

from klima import einlesen
from klima.anomalien import standard_mindestjahre, standard_referenzperiode
from klima.trend import steigung_je_gruppe

JAHRESZEITEN = {12: "Winter", 1: "Winter", 2: "Winter", 3: "Frühling", 4: "Frühling",
                5: "Frühling", 6: "Sommer", 7: "Sommer", 8: "Sommer", 9: "Herbst",
                10: "Herbst", 11: "Herbst"}  # fmt: skip
MINDESTTAGE_JE_MONAT = 20


def stundenwerte_mez(stationen: list[str]) -> pd.DataFrame:
    """Stundenwerte mit MEZ-Zeit, Jahr, Monat und Stunde."""
    werte = einlesen.dwd_stundenwerte(
        stationen=stationen, spalten=["stations_id", "zeit_utc", "temperatur"]
    )
    mez = werte["zeit_utc"] + pd.Timedelta(hours=1)
    return werte.assign(
        stations_id=werte["stations_id"].astype(str),
        mez=mez,
        jahr=mez.dt.year.astype("int16"),
        monat=mez.dt.month.astype("int8"),
        stunde=mez.dt.hour.astype("int8"),
    )


def jahresmittel_je_stunde(
    stundenwerte: pd.DataFrame,
    referenz: tuple[int, int] | None = None,
    mindestjahre: int | None = None,
) -> pd.DataFrame:
    """Jahresmittel der Anomalie je Station, Jahr und Stunde (MEZ).

    1. Monatsmittel je Stunde (mind. 20 Tage mit Wert),
    2. Anomalie gegenüber dem Mittel derselben Stunde und desselben Monats in der Referenzperiode,
    3. Jahresmittel nur aus 12 Monaten.
    So bleibt der Jahresgang außen vor, und fehlende Monate verzerren nichts.
    """
    referenz = referenz or standard_referenzperiode()
    mindestjahre = standard_mindestjahre() if mindestjahre is None else mindestjahre
    schluessel = ["stations_id", "jahr", "monat", "stunde"]
    monat = stundenwerte.groupby(schluessel)["temperatur"].agg(["mean", "count"]).reset_index()
    monat = monat[monat["count"] >= MINDESTTAGE_JE_MONAT]

    in_ref = monat[monat["jahr"].between(*referenz)]
    klima = in_ref.groupby(["stations_id", "monat", "stunde"])["mean"].agg(["mean", "count"])
    klima = klima[klima["count"] >= mindestjahre]["mean"].rename("klima").reset_index()
    monat = monat.merge(klima, on=["stations_id", "monat", "stunde"])
    monat["anomalie"] = monat["mean"] - monat["klima"]

    jahr = monat.groupby(["stations_id", "jahr", "stunde"])["anomalie"].agg(["mean", "count"])
    jahr = jahr[jahr["count"] == 12]["mean"].rename("anomalie")
    return jahr.reset_index()


def jahrzehnte_je_stunde(jahre: pd.DataFrame, mindestjahre: int = 7) -> pd.DataFrame:
    """Mittlere Anomalie je Station, Jahrzehnt und Stunde (Jahrzehnt mit mind. 7 Jahren)."""
    mit_jahrzehnt = jahre.assign(jahrzehnt=(jahre["jahr"] // 10) * 10)
    mittel = mit_jahrzehnt.groupby(["stations_id", "jahrzehnt", "stunde"])["anomalie"].agg(
        ["mean", "count"]
    )
    return mittel[mittel["count"] >= mindestjahre]["mean"].rename("anomalie").reset_index()


def trend_je_stunde(
    jahre: pd.DataFrame, von: int = 1951, bis: int | None = None, mindestanteil: float = 0.8
) -> pd.DataFrame:
    """Linearer Trend (°C/Dekade) je Station und Stunde; nur mit ≥ 80 % Jahren im Zeitraum."""
    bis = bis or int(jahre["jahr"].max())
    zeitraum = jahre[jahre["jahr"].between(von, bis)].copy()
    zeitraum["gruppe"] = zeitraum["stations_id"] + "_" + zeitraum["stunde"].astype(str)
    anzahl = zeitraum.groupby("gruppe")["jahr"].transform("count")
    zeitraum = zeitraum[anzahl >= mindestanteil * (bis - von + 1)]
    steigung = steigung_je_gruppe(zeitraum, "gruppe", "jahr", "anomalie") * 10
    ergebnis = steigung.rename("trend").reset_index()
    ergebnis[["stations_id", "stunde"]] = ergebnis["gruppe"].str.split("_", expand=True)
    return ergebnis.astype({"stunde": int}).drop(columns="gruppe")


def waermeinsel(stundenwerte: pd.DataFrame, stadt: str, land: str) -> pd.DataFrame:
    """Mittlere Temperaturdifferenz Stadt − Land je Jahreszeit und Stunde (MEZ).

    Nur Stunden, in denen beide Stationen messen. Ergebnis: `jahreszeit`, `stunde`,
    `differenz`, `stunden` (Anzahl gemeinsamer Werte), plus Zeitraum `von`/`bis`.
    """
    a = stundenwerte[stundenwerte["stations_id"] == stadt].set_index("mez")["temperatur"]
    b = stundenwerte[stundenwerte["stations_id"] == land].set_index("mez")["temperatur"]
    gemeinsam = pd.concat({"stadt": a, "land": b}, axis=1, join="inner").dropna()
    if gemeinsam.empty:
        raise ValueError(f"Keine gemeinsamen Stundenwerte für {stadt} und {land}.")
    gemeinsam["differenz"] = gemeinsam["stadt"] - gemeinsam["land"]
    gemeinsam["jahreszeit"] = gemeinsam.index.month.map(JAHRESZEITEN)
    gemeinsam["stunde"] = gemeinsam.index.hour
    ergebnis = (
        gemeinsam.groupby(["jahreszeit", "stunde"])["differenz"]
        .agg(differenz="mean", stunden="count")
        .reset_index()
    )
    return ergebnis.assign(von=gemeinsam.index.min().year, bis=gemeinsam.index.max().year)
