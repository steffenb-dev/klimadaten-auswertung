"""Lade-Schnittstelle für Notebooks und Analysen.

Alle Funktionen lesen aus `daten/aufbereitet/` und laden nur die benötigten Spalten und
Zeilen. Fehlt die Aufbereitung oder ist sie veraltet, wird sie automatisch erzeugt.

Beispiel:

    from klima import einlesen
    stationen = einlesen.ghcnm_stationen(laender=["GM"])
    werte = einlesen.ghcnm_monatswerte("qcf", stationen=stationen.stations_id, von=1951, bis=1980)
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import pandas as pd
import xarray as xr

from klima.aufbereiten import Aufbereitung
from klima.konfiguration import projektwurzel, rohverzeichnis

GHCNM_VARIANTEN = ("qcu", "qcf", "qfe")


def aufbereitungsverzeichnis() -> Path:
    return projektwurzel() / "daten" / "aufbereitet"


def _ordner(datensatz: str) -> Path:
    return Aufbereitung(rohverzeichnis(), aufbereitungsverzeichnis()).sicherstellen(datensatz)


def _jahresfilter(von: int | None, bis: int | None) -> list[tuple]:
    filter_ = []
    if von is not None:
        filter_.append(("jahr", ">=", von))
    if bis is not None:
        filter_.append(("jahr", "<=", bis))
    return filter_


def _lies(pfad: Path, filter_: list[tuple], spalten: list[str] | None) -> pd.DataFrame:
    return pd.read_parquet(pfad, columns=spalten, filters=filter_ or None)


def _ghcnm_datensatz(variante: str) -> str:
    if variante not in GHCNM_VARIANTEN:
        raise ValueError(f"Unbekannte GHCNm-Variante {variante!r}, erlaubt: {GHCNM_VARIANTEN}")
    return f"ghcnm_{variante}"


# --- GHCN-Monthly ----------------------------------------------------------------


def ghcnm_stationen(variante: str = "qcf", laender: Iterable[str] | None = None) -> pd.DataFrame:
    """Stationen von GHCNm, optional nach FIPS-Ländercodes gefiltert (z. B. `["GM"]`).

    Ist die Länderliste geladen, wird die Spalte `land_name` ergänzt.
    """
    filter_ = [("land", "in", list(laender))] if laender is not None else []
    stationen = _lies(_ordner(_ghcnm_datensatz(variante)) / "stationen.parquet", filter_, None)
    try:
        laender_tabelle = pd.read_parquet(_ordner("ghcnm_laender") / "laender.parquet")
    except FileNotFoundError:
        return stationen
    position = stationen.columns.get_loc("land") + 1
    stationen = stationen.merge(laender_tabelle, on="land", how="left")
    spalten = list(stationen.columns)
    spalten.insert(position, spalten.pop(spalten.index("land_name")))
    return stationen[spalten]


def ghcnm_monatswerte(
    variante: str = "qcf",
    stationen: Iterable[str] | None = None,
    von: int | None = None,
    bis: int | None = None,
    nur_ohne_qc_flag: bool = True,
    spalten: list[str] | None = None,
) -> pd.DataFrame:
    """Monatsmittel der Temperatur (°C) im Long-Format.

    `nur_ohne_qc_flag` entfernt Werte, die die NOAA-Qualitätskontrolle markiert hat
    (relevant für QCU; in QCF sind markierte Werte bereits entfernt).
    """
    filter_ = _jahresfilter(von, bis)
    if stationen is not None:
        filter_.append(("stations_id", "in", list(stationen)))
    if nur_ohne_qc_flag and spalten is not None and "qc_flag" not in spalten:
        spalten = [*spalten, "qc_flag"]
        entfernen = True
    else:
        entfernen = False

    werte = _lies(_ordner(_ghcnm_datensatz(variante)) / "monatswerte.parquet", filter_, spalten)
    if nur_ohne_qc_flag:
        werte = werte[werte["qc_flag"].isna()]
    if entfernen:
        werte = werte.drop(columns="qc_flag")
    werte = werte.reset_index(drop=True)
    if "stations_id" in werte:
        werte["stations_id"] = werte["stations_id"].cat.remove_unused_categories()
    return werte


# --- ERSST ------------------------------------------------------------------------


def ersst(
    von: int | str | None = None,
    bis: int | str | None = None,
    breite: tuple[float, float] | None = None,
    laenge: tuple[float, float] | None = None,
) -> xr.Dataset:
    """Meeresoberflächentemperatur als `xarray.Dataset` mit `sst(zeit, breite, laenge)`.

    `von`/`bis` als Jahr oder `"JJJJ-MM"`; `breite`/`laenge` als (min, max) in Grad,
    Längen im Bereich 0–360.
    """
    auswahl: dict[str, slice] = {}
    if von is not None or bis is not None:
        auswahl["zeit"] = slice(
            str(von) if von is not None else None, str(bis) if bis is not None else None
        )
    if breite is not None:
        auswahl["breite"] = slice(*breite)
    if laenge is not None:
        auswahl["laenge"] = slice(*laenge)
    with xr.open_dataset(_ordner("ersst_v5") / "sst.nc") as ds:
        return ds.sel(auswahl).load()


# --- Vergleichsreihen ---------------------------------------------------------------


def gistemp(
    gebiet: str | None = "global",
    art: str | None = "land_ozean",
    von: int | None = None,
    bis: int | None = None,
) -> pd.DataFrame:
    """GISTEMP-Anomalien (°C, Referenz 1951–1980).

    `gebiet`: `global`, `nordhalbkugel`, `suedhalbkugel`; `art`: `land_ozean`, `land`;
    jeweils `None` für alle.
    """
    filter_ = _jahresfilter(von, bis)
    if gebiet is not None:
        filter_.append(("gebiet", "==", gebiet))
    if art is not None:
        filter_.append(("art", "==", art))
    return _lies(_ordner("gistemp") / "reihen.parquet", filter_, None).reset_index(drop=True)


def hadcrut5(
    gebiet: str | None = "global",
    variante: str | None = "nicht_aufgefuellt",
    von: int | None = None,
    bis: int | None = None,
) -> pd.DataFrame:
    """HadCRUT5-Jahresanomalien (°C, Referenz 1961–1990) mit 95-%-Unsicherheitsbereich.

    `gebiet`: `global`, `nordhalbkugel`, `suedhalbkugel`; `variante`: `nicht_aufgefuellt`
    (nur Zellen mit Messungen – wie unsere Methode) oder `aufgefuellt`; `None` für alle.
    """
    filter_ = _jahresfilter(von, bis)
    if gebiet is not None:
        filter_.append(("gebiet", "==", gebiet))
    if variante is not None:
        filter_.append(("variante", "==", variante))
    return _lies(_ordner("hadcrut5") / "reihen.parquet", filter_, None).reset_index(drop=True)


# --- DWD ----------------------------------------------------------------------------


def dwd_stationen(aufloesung: str = "monat") -> pd.DataFrame:
    """DWD-Stationsliste für `aufloesung` = `"tag"` oder `"monat"`."""
    if aufloesung not in ("tag", "monat"):
        raise ValueError("aufloesung muss 'tag' oder 'monat' sein.")
    return pd.read_parquet(_ordner("dwd_stationen") / f"stationen_{aufloesung}.parquet")


def dwd_gebietsmittel(
    groesse: str = "temperatur",
    gebiete: Iterable[str] | None = ("Deutschland",),
    von: int | None = None,
    bis: int | None = None,
) -> pd.DataFrame:
    """Monatliche DWD-Gebietsmittel; `groesse` = `"temperatur"` (°C) oder `"niederschlag"` (mm).

    `gebiete=None` liefert alle Bundesländer und Kombinationen.
    """
    if groesse not in ("temperatur", "niederschlag"):
        raise ValueError("groesse muss 'temperatur' oder 'niederschlag' sein.")
    filter_ = _jahresfilter(von, bis)
    if gebiete is not None:
        filter_.append(("gebiet", "in", list(gebiete)))
    pfad = _ordner(f"dwd_gebietsmittel_{groesse}") / "monatswerte.parquet"
    return _lies(pfad, filter_, None).reset_index(drop=True)


def dwd_monatswerte(
    stationen: Iterable[str] | None = None,
    von: int | None = None,
    bis: int | None = None,
    spalten: list[str] | None = None,
) -> pd.DataFrame:
    """Monatswerte der DWD-Stationen (historisch + aktuell zusammengeführt).

    Spalten u. a. `tmittel`, `tmax_mittel`, `tmin_mittel` (°C), `niederschlag` (mm),
    `sonnenschein` (h); Stations-IDs 5-stellig, z. B. `"03987"` für Potsdam.
    """
    filter_ = _jahresfilter(von, bis)
    if stationen is not None:
        filter_.append(("stations_id", "in", [str(s).zfill(5) for s in stationen]))
    werte = _lies(_ordner("dwd_monatswerte") / "monatswerte.parquet", filter_, spalten)
    if "stations_id" in werte:
        werte["stations_id"] = werte["stations_id"].cat.remove_unused_categories()
    return werte


def dwd_tageswerte(
    stationen: Iterable[str] | None = None,
    von: int | None = None,
    bis: int | None = None,
    spalten: list[str] | None = None,
) -> pd.DataFrame:
    """Tageswerte der DWD-Stationen (historisch + aktuell zusammengeführt).

    Spalten u. a. `datum`, `jahr`, `tmittel`, `tmax`, `tmin` (°C), `niederschlag` (mm),
    `sonnenschein` (h), `schneehoehe` (cm). `von`/`bis` filtern nach Jahr.
    """
    filter_ = _jahresfilter(von, bis)
    if stationen is not None:
        filter_.append(("stations_id", "in", [str(s).zfill(5) for s in stationen]))
    werte = _lies(_ordner("dwd_tageswerte") / "tageswerte.parquet", filter_, spalten)
    if "stations_id" in werte:
        werte["stations_id"] = werte["stations_id"].cat.remove_unused_categories()
    return werte
