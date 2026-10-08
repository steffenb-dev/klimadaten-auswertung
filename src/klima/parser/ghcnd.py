"""Parser für GHCN-Daily (NOAA NCEI): Stationsliste, Inventar und Stationsdateien.

Formate laut `readme.txt` bzw. `readme-by_station.txt` von NOAA:

    ghcnd-stations.txt   ID 1-11, LATITUDE 13-20, LONGITUDE 22-30, ELEVATION 32-37,
                         STATE 39-40, NAME 42-71, GSN 73-75, HCN/CRN 77-79, WMO-ID 81-85
    ghcnd-inventory.txt  ID 1-11, LATITUDE 13-20, LONGITUDE 22-30, ELEMENT 32-35,
                         FIRSTYEAR 37-40, LASTYEAR 42-45
    <ID>.csv.gz          ID, DATUM (JJJJMMTT), ELEMENT, WERT, M-FLAG, Q-FLAG, S-FLAG, OBS-TIME
                         Temperatur in 1/10 °C, Niederschlag in 1/10 mm, Schneehöhe in mm

Werte mit gesetztem Q-FLAG (nicht bestandene Qualitätsprüfung) werden verworfen.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from klima.archiv import oeffne_text

# GHCN-Element -> (eigene Spalte, Umrechnungsfaktor)
ELEMENTE = {
    "TMAX": ("tmax", 0.1),
    "TMIN": ("tmin", 0.1),
    "TAVG": ("tmittel", 0.1),
    "PRCP": ("niederschlag", 0.1),
    "SNWD": ("schneehoehe", 0.1),  # mm -> cm
}


def lies_stationen(pfad: Path) -> pd.DataFrame:
    """Stationsliste: `stations_id`, `land`, `breite`, `laenge`, `hoehe`, `name`, `wmo_id`."""
    with oeffne_text(pfad, encoding="latin-1") as datei:
        stationen = pd.read_fwf(
            datei,
            colspecs=[(0, 11), (12, 20), (21, 30), (31, 37), (41, 71), (80, 85)],
            names=["stations_id", "breite", "laenge", "hoehe", "name", "wmo_id"],
            dtype={"stations_id": str, "name": str, "wmo_id": str},
        )
    stationen["hoehe"] = stationen["hoehe"].where(stationen["hoehe"] > -999)
    stationen.insert(1, "land", stationen["stations_id"].str[:2])
    return stationen.astype({"breite": "float32", "laenge": "float32", "hoehe": "float32"})


def lies_inventar(pfad: Path) -> pd.DataFrame:
    """Inventar: je Station und Element der erste und letzte Jahrgang."""
    with oeffne_text(pfad, encoding="latin-1") as datei:
        inventar = pd.read_fwf(
            datei,
            colspecs=[(0, 11), (31, 35), (36, 40), (41, 45)],
            names=["stations_id", "element", "von", "bis"],
            dtype={"stations_id": str, "element": str},
        )
    return inventar.astype({"von": "int16", "bis": "int16", "element": "category"})


def lies_station(pfad: Path) -> pd.DataFrame:
    """Tageswerte einer Station (`<ID>.csv.gz`) im Breitformat.

    Spalten: `stations_id`, `datum`, `jahr`, `tmax`, `tmin`, `tmittel`, `niederschlag`,
    `schneehoehe`.
    """
    with oeffne_text(pfad) as datei:
        lang = pd.read_csv(
            datei,
            header=None,
            names=["stations_id", "datum", "element", "wert", "m", "q", "s", "zeit"],
            usecols=["stations_id", "datum", "element", "wert", "q"],
            dtype={"stations_id": str, "datum": str, "element": str, "q": str},
        )
    lang = lang[lang["element"].isin(list(ELEMENTE)) & lang["q"].isna()]
    breit = lang.pivot_table(
        index=["stations_id", "datum"], columns="element", values="wert", aggfunc="first"
    )
    ergebnis = pd.DataFrame(index=breit.index).reset_index()
    for element, (spalte, faktor) in ELEMENTE.items():
        werte = breit[element].to_numpy() * faktor if element in breit else float("nan")
        ergebnis[spalte] = pd.Series(werte, index=ergebnis.index, dtype="float32")
    ergebnis["datum"] = pd.to_datetime(ergebnis["datum"], format="%Y%m%d")
    ergebnis.insert(2, "jahr", ergebnis["datum"].dt.year.astype("int16"))
    return ergebnis


def lies_stationen_alle(dateien: list[Path]) -> pd.DataFrame:
    teile = [lies_station(p) for p in sorted(dateien)]
    alle = pd.concat(teile, ignore_index=True).sort_values(["stations_id", "datum"])
    return alle.reset_index(drop=True).astype({"stations_id": "category"})
