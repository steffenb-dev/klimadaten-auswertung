"""Bestandsübersicht: Welche Messstationen liegen lokal vor – mit welchen Daten?

Liest ausschließlich die aufbereiteten Parquet-Dateien und fasst je Quelle, Station und
zeitlicher Auflösung zusammen: Name, Land, Koordinaten, Messgrößen, Zeitraum und
Vollständigkeit. Datensätze ohne lokale Rohdaten werden übersprungen.

Neue Quellen (z. B. Tageswerte in M6) werden ergänzt, indem `QUELLEN` eine weitere
Funktion erhält, die eine Tabelle mit den Spalten aus `SPALTEN` liefert.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

import numpy as np
import pandas as pd

from klima import einlesen
from klima.aufbereiten import RohdatenFehlen

SPALTEN = [
    "quelle", "stations_id", "name", "land", "land_name", "region",
    "breite", "laenge", "hoehe",
    "aufloesung", "messgroessen", "von", "bis", "werte", "vollstaendigkeit",
]  # fmt: skip

DWD_MESSGROESSEN = {
    "tmittel": "Temperatur",
    "tmax_mittel": "Temperatur-Maximum",
    "tmin_mittel": "Temperatur-Minimum",
    "niederschlag": "Niederschlag",
    "sonnenschein": "Sonnenschein",
}


def _zeitraeume(
    werte: pd.DataFrame, zeitindex: pd.Series, messgroessen: dict[str, str]
) -> pd.DataFrame:
    """Kleinster/größter Zeitindex, Anzahl Zeitschritte mit Daten und Messgrößen je Station.

    Ein Zeitschritt zählt, wenn mindestens eine der Messgrößen einen Wert hat.
    """
    spalten = list(messgroessen)
    vorhanden = werte[spalten].notna()
    mit_daten = vorhanden.any(axis=1).to_numpy()
    stationen = werte["stations_id"].astype(str)[mit_daten]
    hilfs = pd.DataFrame({"stations_id": stationen, "index": zeitindex[mit_daten]})
    zeitraum = hilfs.groupby("stations_id")["index"].agg(["min", "max", "count"])
    je_groesse = vorhanden[mit_daten].groupby(stationen).any()
    zeitraum["messgroessen"] = je_groesse.apply(
        lambda zeile: ", ".join(messgroessen[s] for s in spalten if zeile[s]), axis=1
    )
    zeitraum["werte"] = zeitraum["count"]
    zeitraum["vollstaendigkeit"] = (
        zeitraum["count"] / (zeitraum["max"] - zeitraum["min"] + 1) * 100
    ).astype("float32")
    return zeitraum


def _monatliche_zeitraeume(werte: pd.DataFrame, messgroessen: dict[str, str]) -> pd.DataFrame:
    """Zeiträume aus Monatswerten; `von` = Monatserster, `bis` = Monatsletzter."""
    monatsindex = werte["jahr"].astype(np.int32) * 12 + werte["monat"].astype(np.int32) - 1
    zeitraum = _zeitraeume(werte, monatsindex, messgroessen)
    von = pd.PeriodIndex.from_fields(
        year=zeitraum["min"] // 12, month=zeitraum["min"] % 12 + 1, freq="M"
    )
    bis = pd.PeriodIndex.from_fields(
        year=zeitraum["max"] // 12, month=zeitraum["max"] % 12 + 1, freq="M"
    )
    zeitraum["von"] = von.to_timestamp(how="start").normalize()
    zeitraum["bis"] = bis.to_timestamp(how="end").normalize()
    return zeitraum.drop(columns=["min", "max", "count"]).reset_index()


def _taegliche_zeitraeume(werte: pd.DataFrame, messgroessen: dict[str, str]) -> pd.DataFrame:
    """Zeiträume aus Tageswerten (Spalte `datum`)."""
    tagesindex = (pd.to_datetime(werte["datum"]) - pd.Timestamp("1700-01-01")).dt.days
    zeitraum = _zeitraeume(werte, tagesindex, messgroessen)
    zeitraum["von"] = pd.Timestamp("1700-01-01") + pd.to_timedelta(zeitraum["min"], unit="D")
    zeitraum["bis"] = pd.Timestamp("1700-01-01") + pd.to_timedelta(zeitraum["max"], unit="D")
    return zeitraum.drop(columns=["min", "max", "count"]).reset_index()


def _laendernamen() -> dict[str, str]:
    try:
        laender = pd.read_parquet(einlesen._ordner("ghcnm_laender") / "laender.parquet")
    except RohdatenFehlen:
        return {}
    return dict(zip(laender["land"], laender["land_name"], strict=True))


def _ghcnm(variante: str) -> Callable[[dict[str, str]], pd.DataFrame]:
    def uebersicht(laendernamen: dict[str, str]) -> pd.DataFrame:
        stationen = einlesen.ghcnm_stationen(variante)
        werte = einlesen.ghcnm_monatswerte(
            variante, nur_ohne_qc_flag=False, spalten=["stations_id", "jahr", "monat", "tavg"]
        )
        zeitraeume = _monatliche_zeitraeume(werte, {"tavg": "Temperatur"})
        tabelle = stationen.astype({"stations_id": str}).merge(zeitraeume, on="stations_id")
        return tabelle.assign(
            quelle=f"GHCNm {variante.upper()}",
            land_name=tabelle["land"].map(laendernamen),
            region=pd.NA,
            aufloesung="monatlich",
        )

    return uebersicht


def _dwd_monat(laendernamen: dict[str, str]) -> pd.DataFrame:
    stationen = einlesen.dwd_stationen("monat")
    werte = einlesen.dwd_monatswerte(spalten=["stations_id", "jahr", "monat", *DWD_MESSGROESSEN])
    zeitraeume = _monatliche_zeitraeume(werte, DWD_MESSGROESSEN)
    tabelle = stationen.drop(columns=["von", "bis"]).merge(zeitraeume, on="stations_id")
    return tabelle.assign(
        quelle="DWD",
        land="GM",
        land_name=laendernamen.get("GM", "Germany"),
        region=tabelle["bundesland"].astype(str),
        aufloesung="monatlich",
    )


DWD_TAG_MESSGROESSEN = {
    "tmittel": "Temperatur",
    "tmax": "Temperatur-Maximum",
    "tmin": "Temperatur-Minimum",
    "niederschlag": "Niederschlag",
    "sonnenschein": "Sonnenschein",
    "schneehoehe": "Schneehöhe",
}


def _dwd_tag(laendernamen: dict[str, str]) -> pd.DataFrame:
    stationen = einlesen.dwd_stationen("tag")
    werte = einlesen.dwd_tageswerte(spalten=["stations_id", "datum", *DWD_TAG_MESSGROESSEN])
    zeitraeume = _taegliche_zeitraeume(werte, DWD_TAG_MESSGROESSEN)
    tabelle = stationen.drop(columns=["von", "bis"]).merge(zeitraeume, on="stations_id")
    return tabelle.assign(
        quelle="DWD",
        land="GM",
        land_name=laendernamen.get("GM", "Germany"),
        region=tabelle["bundesland"].astype(str),
        aufloesung="täglich",
    )


def _ghcnd_tag(laendernamen: dict[str, str]) -> pd.DataFrame:
    werte = einlesen.ghcnd_tageswerte(
        spalten=["stations_id", "datum", "tmax", "tmin", "niederschlag", "schneehoehe"]
    )
    messgroessen = {k: v for k, v in DWD_TAG_MESSGROESSEN.items() if k in werte}
    zeitraeume = _taegliche_zeitraeume(werte, messgroessen)
    stationen = einlesen.ghcnd_stationen().astype({"stations_id": str})
    tabelle = stationen.merge(zeitraeume, on="stations_id")
    return tabelle.assign(
        quelle="GHCN-Daily",
        land_name=tabelle["land"].map(laendernamen),
        region=pd.NA,
        aufloesung="täglich",
    )


# Quelle -> Funktion, die die Übersicht für diese Quelle liefert
QUELLEN: dict[str, Callable[[dict[str, str]], pd.DataFrame]] = {
    "ghcnm_qcu": _ghcnm("qcu"),
    "ghcnm_qcf": _ghcnm("qcf"),
    "ghcnm_qfe": _ghcnm("qfe"),
    "dwd_monat": _dwd_monat,
    "dwd_tag": _dwd_tag,
    "ghcnd": _ghcnd_tag,
}


def stationsuebersicht(
    quellen: Iterable[str] | None = None,
    laender: Iterable[str] | None = None,
    name: str | None = None,
    aufloesung: str | None = None,
) -> pd.DataFrame:
    """Übersicht aller lokal vorhandenen Messstationen.

    Filter:
    - `quellen`: Schlüssel aus `QUELLEN`, z. B. `["dwd_monat"]`
    - `laender`: FIPS-Codes (`"GM"`) oder Teile des Ländernamens (`"germ"`)
    - `name`: Teil des Stationsnamens (ohne Groß-/Kleinschreibung)
    - `aufloesung`: `"monatlich"` oder `"täglich"`

    Spalten siehe `SPALTEN`; `von`/`bis` sind Daten (bei Monatswerten Monatserster bzw.
    -letzter), `vollstaendigkeit` ist der Anteil der Zeitschritte (Monate bzw. Tage) mit
    Daten zwischen `von` und `bis` in Prozent.
    """
    auswahl = list(quellen) if quellen is not None else list(QUELLEN)
    unbekannt = [q for q in auswahl if q not in QUELLEN]
    if unbekannt:
        raise ValueError(f"Unbekannte Quellen: {unbekannt}. Verfügbar: {list(QUELLEN)}")

    laendernamen = _laendernamen()
    teile = []
    for quelle in auswahl:
        try:
            teile.append(QUELLEN[quelle](laendernamen))
        except RohdatenFehlen:
            continue  # nicht heruntergeladen -> nicht im Bestand
    if not teile:
        return pd.DataFrame(columns=SPALTEN)
    tabelle = pd.concat([t[SPALTEN] for t in teile], ignore_index=True)

    if laender is not None:
        muster = [str(land).lower() for land in laender]
        codes = tabelle["land"].str.lower()
        namen = tabelle["land_name"].fillna("").str.lower()
        treffer = pd.Series(False, index=tabelle.index)
        for m in muster:
            treffer |= (codes == m) | namen.str.contains(m, regex=False)
        tabelle = tabelle[treffer]
    if name is not None:
        tabelle = tabelle[tabelle["name"].str.contains(name, case=False, regex=False)]
    if aufloesung is not None:
        tabelle = tabelle[tabelle["aufloesung"] == aufloesung]

    tabelle = tabelle.astype({"quelle": "category", "land": "category", "aufloesung": "category"})
    return tabelle.sort_values(["land", "name", "quelle"], ignore_index=True)


def zusammenfassung(uebersicht: pd.DataFrame) -> pd.DataFrame:
    """Kennzahlen je Quelle und Auflösung: Stationen, Länder, frühester/spätester Monat."""
    return (
        uebersicht.groupby(["quelle", "aufloesung"], observed=True)
        .agg(
            stationen=("stations_id", "count"),
            laender=("land", "nunique"),
            von=("von", "min"),
            bis=("bis", "max"),
            werte=("werte", "sum"),
        )
        .reset_index()
    )
