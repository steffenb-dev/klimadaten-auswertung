"""Parser für Daten des Deutschen Wetterdienstes (Climate Data Center).

Die Dateien sind Latin-1-kodiert. Fehlwerte kennzeichnet der DWD mit -999.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from klima.archiv import oeffne_text

KODIERUNG = "latin-1"
FEHLWERT = -999

# Stationslisten: Die Strichlinie unter der Kopfzeile passt nicht zu den Datenspalten.
# Die Zahlenfelder werden daher per regulärem Ausdruck gelesen, Name und Bundesland
# über ihre feste Breite von je 41 Zeichen.
_STATION_ZAHLEN = re.compile(r"^\s*(\d+)\s+(\d{8})\s+(\d{8})\s+(-?\d+)\s+(-?[\d.]+)\s+(-?[\d.]+) ")
_NAMENSBREITE = 41


def lies_stationsliste(pfad: Path) -> pd.DataFrame:
    """Stationsbeschreibung (`*_Beschreibung_Stationen.txt`).

    Spalten: `stations_id` (5-stellig), `von`, `bis`, `hoehe`, `breite`, `laenge`,
    `name`, `bundesland`, `abgabe`.
    """
    zeilen = []
    with oeffne_text(pfad, encoding=KODIERUNG) as datei:
        for nummer, zeile in enumerate(datei):
            if nummer < 2 or not zeile.strip():
                continue  # Kopfzeile und Strichlinie
            treffer = _STATION_ZAHLEN.match(zeile)
            if not treffer:
                raise ValueError(f"{pfad.name}, Zeile {nummer + 1}: unerwartetes Format")
            rest = zeile[treffer.end() :].rstrip("\r\n")
            zeilen.append(
                (
                    *treffer.groups(),
                    rest[:_NAMENSBREITE].strip(),
                    rest[_NAMENSBREITE : 2 * _NAMENSBREITE].strip(),
                    rest[2 * _NAMENSBREITE :].strip(),
                )
            )
    stationen = pd.DataFrame(
        zeilen,
        columns=[
            "stations_id", "von", "bis", "hoehe", "breite", "laenge",
            "name", "bundesland", "abgabe",
        ],
    )  # fmt: skip
    stationen["stations_id"] = stationen["stations_id"].str.zfill(5)
    stationen["von"] = pd.to_datetime(stationen["von"], format="%Y%m%d")
    stationen["bis"] = pd.to_datetime(stationen["bis"], format="%Y%m%d")
    return stationen.astype(
        {"hoehe": "float32", "breite": "float32", "laenge": "float32", "bundesland": "category"}
    )


def lies_gebietsmittel(pfad: Path, groesse: str) -> pd.DataFrame:
    """Monatliche Gebietsmittel (`regional_averages_XX_MM.txt`) als Long-Format.

    Spalten: `gebiet`, `jahr`, `monat`, `<groesse>` (z. B. `temperatur` in °C,
    `niederschlag` in mm).
    """
    with oeffne_text(pfad, encoding=KODIERUNG) as datei:
        tabelle = pd.read_csv(datei, sep=";", skiprows=1, na_values=[FEHLWERT, str(FEHLWERT)])
    tabelle = tabelle.loc[:, ~tabelle.columns.str.startswith("Unnamed")]
    lang = tabelle.melt(id_vars=["Jahr", "Monat"], var_name="gebiet", value_name=groesse)
    lang = lang.dropna(subset=[groesse]).rename(columns={"Jahr": "jahr", "Monat": "monat"})
    return lang[["gebiet", "jahr", "monat", groesse]].astype(
        {"jahr": "int16", "monat": "int8", groesse: "float32"}
    )


def lies_gebietsmittel_alle(dateien: list[Path], groesse: str) -> pd.DataFrame:
    """Alle zwölf Monatsdateien einer Größe, sortiert nach Gebiet und Zeit."""
    alle = pd.concat([lies_gebietsmittel(p, groesse) for p in dateien], ignore_index=True)
    alle = alle.sort_values(["gebiet", "jahr", "monat"], ignore_index=True)
    return alle.astype({"gebiet": "category"})
