"""Parser für GHCN-Monthly v4 (`.inv` Stationen, `.dat` Monatswerte) direkt aus dem `.tar.gz`.

Format laut `readme.txt` von NOAA:

    .inv  ID 1-11, LATITUDE 13-20, LONGITUDE 22-30, STNELEV 32-37, NAME 39-68
    .dat  ID 1-11, YEAR 12-15, ELEMENT 16-19, danach 12 × (VALUE 5, DMFLAG 1, QCFLAG 1, DSFLAG 1)
          Werte in 1/100 °C, Fehlwert -9999

Die `.dat`-Datei wird blockweise mit numpy zerlegt (feste Zeilenlänge), das ist um
Größenordnungen schneller als zeilenweises Parsen in Python und hält den Speicherbedarf
beim Lesen begrenzt.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import numpy as np
import pandas as pd

from klima.archiv import oeffne, oeffne_text

ZEILENLAENGE = 115  # ohne Zeilenumbruch
FEHLWERT = -9999
BLOCKZEILEN = 200_000
FLAGS = ("dm_flag", "qc_flag", "ds_flag")


def lies_laender(pfad: Path) -> pd.DataFrame:
    """Ländercodes (FIPS) und Namen aus `ghcnm-countries.txt`."""
    with oeffne_text(pfad, encoding="latin-1") as datei:
        zeilen = [z.rstrip() for z in datei if z.strip()]
    return pd.DataFrame(
        {"land": [z[:2] for z in zeilen], "land_name": [z[3:].strip() for z in zeilen]}
    )


def lies_stationen(archiv: Path) -> pd.DataFrame:
    """Stationsliste aus der `.inv`-Datei im Archiv."""
    with oeffne_text(archiv, "*.inv", encoding="latin-1") as datei:
        stationen = pd.read_fwf(
            datei,
            colspecs=[(0, 11), (12, 20), (21, 30), (31, 37), (38, 68)],
            names=["stations_id", "breite", "laenge", "hoehe", "name"],
            dtype={"stations_id": str, "name": str},
        )
    stationen["hoehe"] = stationen["hoehe"].where(stationen["hoehe"] > -999)
    stationen.insert(1, "land", stationen["stations_id"].str[:2])
    return stationen.astype({"breite": "float32", "laenge": "float32", "hoehe": "float32"})


def _zerlege_block(block: bytes) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Zerlegt einen Block vollständiger Zeilen in IDs, Jahre, Werte (n×12) und Flags (n×12×3)."""
    zeilen = np.frombuffer(block, dtype=np.uint8).reshape(-1, ZEILENLAENGE + 1)
    if not (zeilen[:, -1] == ord("\n")).all():
        raise ValueError("GHCNm-Datei hat unerwartete Zeilenlängen.")
    if not (zeilen[:, 15:19] == np.frombuffer(b"TAVG", dtype=np.uint8)).all():
        raise ValueError("GHCNm-Datei enthält andere Elemente als TAVG.")

    ids = np.ascontiguousarray(zeilen[:, 0:11]).view("S11").ravel()
    jahre = np.ascontiguousarray(zeilen[:, 11:15]).view("S4").ravel().astype(np.int16)
    monate = zeilen[:, 19 : 19 + 12 * 8].reshape(-1, 12, 8)
    werte = np.ascontiguousarray(monate[:, :, 0:5]).view("S5")[..., 0].astype(np.int32)
    flags = monate[:, :, 5:8]
    return ids, jahre, werte, flags


def _bloecke(archiv: Path) -> Iterable[bytes]:
    groesse = BLOCKZEILEN * (ZEILENLAENGE + 1)
    with oeffne(archiv, "*.dat") as datei:
        rest = b""
        while daten := datei.read(groesse):
            daten = rest + daten
            ende = len(daten) - len(daten) % (ZEILENLAENGE + 1)
            rest = daten[ende:]
            if ende:
                yield daten[:ende]
        if rest:
            if len(rest) == ZEILENLAENGE:  # letzte Zeile ohne Zeilenumbruch
                yield rest + b"\n"
            else:
                raise ValueError("GHCNm-Datei endet mit unvollständiger Zeile.")


def _flag_kategorien(codes: np.ndarray) -> pd.Categorical:
    """Wandelt Flag-Bytes in eine Kategorie um; Leerzeichen wird zu fehlend (NA)."""
    vorhanden = np.unique(codes)
    vorhanden = vorhanden[vorhanden != ord(" ")]
    tabelle = np.full(256, -1, dtype=np.int16)
    tabelle[vorhanden] = np.arange(len(vorhanden))
    return pd.Categorical.from_codes(tabelle[codes], categories=[chr(c) for c in vorhanden])


def lies_monatswerte(
    archiv: Path,
    stationen: Iterable[str] | None = None,
    von_jahr: int | None = None,
    bis_jahr: int | None = None,
) -> pd.DataFrame:
    """Monatsmittel der Temperatur im Long-Format, Fehlwerte entfernt.

    Spalten: `stations_id`, `jahr`, `monat`, `tavg` (°C), `dm_flag`, `qc_flag`, `ds_flag`.
    Optional wird bereits beim Lesen nach Stationen und Jahren gefiltert.
    """
    auswahl = None if stationen is None else np.array(sorted(stationen), dtype="S11")
    ids_teile, jahre_teile, zeilen_teile, monat_teile, wert_teile = [], [], [], [], []
    flag_teile: list[np.ndarray] = []
    zeilen_versatz = 0

    for block in _bloecke(archiv):
        ids, jahre, werte, flags = _zerlege_block(block)
        behalten = np.ones(len(ids), dtype=bool)
        if auswahl is not None:
            behalten &= np.isin(ids, auswahl)
        if von_jahr is not None:
            behalten &= jahre >= von_jahr
        if bis_jahr is not None:
            behalten &= jahre <= bis_jahr
        ids, jahre, werte, flags = ids[behalten], jahre[behalten], werte[behalten], flags[behalten]

        zeile, monat = np.nonzero(werte != FEHLWERT)
        ids_teile.append(ids)
        jahre_teile.append(jahre)
        zeilen_teile.append(zeile + zeilen_versatz)
        monat_teile.append(monat.astype(np.int8) + 1)
        wert_teile.append(werte[zeile, monat])
        flag_teile.append(flags[zeile, monat])
        zeilen_versatz += len(ids)

    ids = np.concatenate(ids_teile) if ids_teile else np.array([], dtype="S11")
    jahre = np.concatenate(jahre_teile) if jahre_teile else np.array([], dtype=np.int16)
    zeile = np.concatenate(zeilen_teile) if zeilen_teile else np.array([], dtype=np.int64)
    flags = np.concatenate(flag_teile) if flag_teile else np.empty((0, 3), dtype=np.uint8)

    # Stations-IDs als Kategorie: nur ~28.000 verschiedene Werte bei ~17 Mio. Zeilen
    eindeutig, codes = np.unique(ids, return_inverse=True)
    ergebnis = pd.DataFrame(
        {
            "stations_id": pd.Categorical.from_codes(
                codes[zeile], categories=eindeutig.astype(str)
            ),
            "jahr": jahre[zeile],
            "monat": np.concatenate(monat_teile) if monat_teile else np.array([], np.int8),
            "tavg": (np.concatenate(wert_teile) if wert_teile else np.array([], np.int32)).astype(
                np.float32
            )
            / np.float32(100),
        }
    )
    for i, name in enumerate(FLAGS):
        ergebnis[name] = _flag_kategorien(flags[:, i])
    return ergebnis
