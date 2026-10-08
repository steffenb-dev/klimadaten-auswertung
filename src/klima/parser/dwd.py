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


# Kürzel im Dateinamen der jährlichen Gebietsmittel -> Kenngröße
KENNTAGE_KUERZEL = {
    "txas": "sommertage",
    "txbs": "heisse_tage",
    "tnes": "tropennaechte",
    "tnas": "frosttage",
    "txcs": "eistage",
    "rrsfs": "starkniederschlag_10mm",
    "rrsgs": "starkniederschlag_20mm",
}


def lies_jahresgebietsmittel_kenntage(pfad: Path) -> pd.DataFrame:
    """Jährliche Gebietsmittel einer Kenngröße (`regional_averages_<kürzel>_year.txt`).

    Spalten: `kenngroesse`, `gebiet`, `jahr`, `wert` (Anzahl Tage).
    """
    treffer = re.fullmatch(r"regional_averages_(\w+?)_year\.txt", pfad.name)
    if not treffer or treffer[1] not in KENNTAGE_KUERZEL:
        raise ValueError(f"Unbekannte Kenntage-Datei: {pfad.name}")
    with oeffne_text(pfad, encoding=KODIERUNG) as datei:
        tabelle = pd.read_csv(datei, sep=";", skiprows=1, na_values=[FEHLWERT, str(FEHLWERT)])
    tabelle = tabelle.loc[:, ~tabelle.columns.str.startswith("Unnamed")]
    tabelle = tabelle.drop(columns=[s for s in tabelle.columns if s.startswith("Jahr.")])
    lang = tabelle.melt(id_vars="Jahr", var_name="gebiet", value_name="wert").dropna()
    lang = lang.rename(columns={"Jahr": "jahr"})
    lang.insert(0, "kenngroesse", KENNTAGE_KUERZEL[treffer[1]])
    return lang.astype({"jahr": "int16", "wert": "float32"})


def lies_jahresgebietsmittel_kenntage_alle(dateien: list[Path]) -> pd.DataFrame:
    alle = pd.concat([lies_jahresgebietsmittel_kenntage(p) for p in dateien], ignore_index=True)
    alle = alle.sort_values(["kenngroesse", "gebiet", "jahr"], ignore_index=True)
    return alle.astype({"kenngroesse": "category", "gebiet": "category"})


# DWD-Kennung -> eigene Spalte (Tageswerte, Klima-Kollektiv KL)
TAGESWERTE_SPALTEN = {
    "TMK": "tmittel",  # Tagesmittel der Lufttemperatur, °C
    "TXK": "tmax",  # Tagesmaximum, °C
    "TNK": "tmin",  # Tagesminimum in 2 m, °C
    "TGK": "tmin_boden",  # Minimum in 5 cm über dem Boden, °C
    "RSK": "niederschlag",  # Tagessumme, mm
    "RSKF": "niederschlagsform",  # Kennung der Niederschlagsform
    "SDK": "sonnenschein",  # Sonnenscheindauer, Stunden
    "SHK_TAG": "schneehoehe",  # Schneehöhe, cm
    "QN_3": "qn_wind",  # Qualitätsniveau Wind
    "QN_4": "qn_klima",  # Qualitätsniveau der übrigen Größen
}

_STATIONSDATEI = re.compile(r"(?:monats|tages)werte_KL_(\d{5})_(?:(\d{8})_(\d{8})_hist|akt)\.zip")


def _lies_produkt(pfad: Path, muster: str) -> pd.DataFrame:
    with oeffne_text(pfad, muster, encoding=KODIERUNG) as datei:
        tabelle = pd.read_csv(
            datei, sep=";", skipinitialspace=True, na_values=[FEHLWERT, str(FEHLWERT)]
        )
    tabelle.columns = tabelle.columns.str.strip()
    return tabelle


def _uebernehme_spalten(werte: pd.DataFrame, tabelle: pd.DataFrame, spalten: dict) -> None:
    for dwd_name, name in spalten.items():
        spalte = (
            tabelle[dwd_name] if dwd_name in tabelle else pd.Series(float("nan"), tabelle.index)
        )
        werte[name] = spalte.astype("float32")


def lies_monatswerte_station(pfad: Path) -> pd.DataFrame:
    """Monatswerte einer Station aus `monatswerte_KL_*.zip` (historisch oder aktuell)."""
    tabelle = _lies_produkt(pfad, "produkt_klima_*monat_*.txt")
    beginn = tabelle["MESS_DATUM_BEGINN"].astype(str)
    werte = pd.DataFrame(
        {
            "stations_id": tabelle["STATIONS_ID"].astype(str).str.zfill(5),
            "jahr": beginn.str[:4].astype("int16"),
            "monat": beginn.str[4:6].astype("int8"),
        }
    )
    _uebernehme_spalten(werte, tabelle, MONATSWERTE_SPALTEN)
    return werte.astype({"qn_temperatur": "Int8", "qn_niederschlag": "Int8"})


def lies_tageswerte_station(pfad: Path) -> pd.DataFrame:
    """Tageswerte einer Station aus `tageswerte_KL_*.zip` (historisch oder aktuell)."""
    tabelle = _lies_produkt(pfad, "produkt_klima_*tag_*.txt")
    datum = pd.to_datetime(tabelle["MESS_DATUM"].astype(str), format="%Y%m%d")
    werte = pd.DataFrame(
        {
            "stations_id": tabelle["STATIONS_ID"].astype(str).str.zfill(5),
            "datum": datum,
            "jahr": datum.dt.year.astype("int16"),
        }
    )
    _uebernehme_spalten(werte, tabelle, TAGESWERTE_SPALTEN)
    return werte.astype(
        {"niederschlagsform": "Int8", "schneehoehe": "Int16", "qn_wind": "Int8", "qn_klima": "Int8"}
    )


def _zusammenfuehren(dateien: list[Path], lesen, schluessel: list[str]) -> pd.DataFrame:
    """Historische und aktuelle Stationsdateien zusammenführen.

    Bei Überschneidungen haben die geprüften historischen Werte Vorrang. Liegen für eine
    Station mehrere historische Dateien vor, gilt die mit dem spätesten Enddatum.
    """
    historisch: dict[str, tuple[str, Path]] = {}
    aktuell: list[Path] = []
    for pfad in dateien:
        treffer = _STATIONSDATEI.fullmatch(pfad.name)
        if not treffer:
            raise ValueError(f"Unerwarteter Dateiname: {pfad.name}")
        stations_id, _, ende = treffer.groups()
        if ende is None:
            aktuell.append(pfad)
        elif stations_id not in historisch or ende > historisch[stations_id][0]:
            historisch[stations_id] = (ende, pfad)

    teile = [lesen(p) for _, p in sorted(historisch.values(), key=str)]
    teile += [lesen(p) for p in sorted(aktuell)]
    alle = pd.concat(teile, ignore_index=True)
    # Historische Teile stehen vorn -> "first" behält bei Dubletten den geprüften Wert
    alle = alle.drop_duplicates(["stations_id", *schluessel], keep="first")
    alle = alle.sort_values(["stations_id", *schluessel], ignore_index=True)
    return alle.astype({"stations_id": "category"})


def lies_monatswerte_alle(dateien: list[Path]) -> pd.DataFrame:
    """Monatswerte aller Stationen, historisch und aktuell zusammengeführt."""
    return _zusammenfuehren(dateien, lies_monatswerte_station, ["jahr", "monat"])


def lies_tageswerte_alle(dateien: list[Path]) -> pd.DataFrame:
    """Tageswerte aller Stationen, historisch und aktuell zusammengeführt."""
    return _zusammenfuehren(dateien, lies_tageswerte_station, ["datum"])
