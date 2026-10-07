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


# --- Monatswerte je Station (Klima-Kollektiv KL) -----------------------------------

# DWD-Kennung -> eigene Spalte
MONATSWERTE_SPALTEN = {
    "MO_TT": "tmittel",  # Monatsmittel der Lufttemperatur, °C
    "MO_TX": "tmax_mittel",  # Monatsmittel der Tagesmaxima, °C
    "MO_TN": "tmin_mittel",  # Monatsmittel der Tagesminima, °C
    "MX_TX": "tmax_absolut",  # absolutes Maximum, °C
    "MX_TN": "tmin_absolut",  # absolutes Minimum, °C
    "MO_RR": "niederschlag",  # Monatssumme, mm
    "MX_RS": "niederschlag_max_tag",  # größte Tagessumme, mm
    "MO_SD_S": "sonnenschein",  # Sonnenscheindauer, Stunden
    "QN_4": "qn_temperatur",  # Qualitätsniveau der Temperatur-/Sonnenwerte
    "QN_6": "qn_niederschlag",  # Qualitätsniveau des Niederschlags
}
_MONATSDATEI = re.compile(r"monatswerte_KL_(\d{5})_(?:(\d{8})_(\d{8})_hist|akt)\.zip")


def lies_monatswerte_station(pfad: Path) -> pd.DataFrame:
    """Monatswerte einer Station aus `monatswerte_KL_*.zip` (historisch oder aktuell)."""
    with oeffne_text(pfad, "produkt_klima_monat_*.txt", encoding=KODIERUNG) as datei:
        tabelle = pd.read_csv(
            datei, sep=";", skipinitialspace=True, na_values=[FEHLWERT, str(FEHLWERT)]
        )
    tabelle.columns = tabelle.columns.str.strip()
    beginn = tabelle["MESS_DATUM_BEGINN"].astype(str)
    werte = pd.DataFrame(
        {
            "stations_id": tabelle["STATIONS_ID"].astype(str).str.zfill(5),
            "jahr": beginn.str[:4].astype("int16"),
            "monat": beginn.str[4:6].astype("int8"),
        }
    )
    for dwd_name, name in MONATSWERTE_SPALTEN.items():
        spalte = (
            tabelle[dwd_name] if dwd_name in tabelle else pd.Series(float("nan"), tabelle.index)
        )
        werte[name] = spalte.astype("float32")
    return werte.astype({"qn_temperatur": "Int8", "qn_niederschlag": "Int8"})


def lies_monatswerte_alle(dateien: list[Path]) -> pd.DataFrame:
    """Alle Stationen, historische und aktuelle Dateien zusammengeführt.

    Bei Überschneidungen haben die geprüften historischen Werte Vorrang. Liegen für eine
    Station mehrere historische Dateien vor, gilt die mit dem spätesten Enddatum.
    """
    historisch: dict[str, tuple[str, Path]] = {}
    aktuell: list[Path] = []
    for pfad in dateien:
        treffer = _MONATSDATEI.fullmatch(pfad.name)
        if not treffer:
            raise ValueError(f"Unerwarteter Dateiname: {pfad.name}")
        stations_id, _, ende = treffer.groups()
        if ende is None:
            aktuell.append(pfad)
        elif stations_id not in historisch or ende > historisch[stations_id][0]:
            historisch[stations_id] = (ende, pfad)

    teile = [lies_monatswerte_station(p) for _, p in sorted(historisch.values(), key=str)]
    teile += [lies_monatswerte_station(p) for p in sorted(aktuell)]
    alle = pd.concat(teile, ignore_index=True)
    # Historische Teile stehen vorn -> "first" behält bei Dubletten den geprüften Wert
    alle = alle.drop_duplicates(["stations_id", "jahr", "monat"], keep="first")
    alle = alle.sort_values(["stations_id", "jahr", "monat"], ignore_index=True)
    return alle.astype({"stations_id": "category"})
