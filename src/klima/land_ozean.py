"""Globale Temperatur aus Land (GHCNm) und Ozean (ERSST v5) – Meilenstein M5.

Verfahren (SPEC.md, Abschnitt 3.1, Schritte 4–7):
1. **Ozean**: ERSST-Meeresoberflächentemperatur je 2°-Zelle. Zellen unter Meereis zeigen
   ERSST-seitig den Gefrierpunkt (−1,8 °C) und gelten wie bei HadCRUT/GISTEMP als fehlend.
   Anomalie je Zelle und Kalendermonat gegenüber der Referenzperiode, dann flächengewichtet
   auf das 5°-Gitter gemittelt.
2. **Land**: Gitteranomalien aus GHCNm wie in M4 (`klima.weltweit`).
3. **Landanteil** je 5°-Zelle aus der Landmaske von Natural Earth (1:50 Mio.).
4. **Kombination** je Zelle und Monat: Landanteil × Land + (1 − Landanteil) × Ozean; liegt nur
   einer der beiden Werte vor, wird dieser verwendet.
5. Flächengewichtetes Mittel über alle besetzten Zellen (global, Halbkugeln).

Wichtig für den Vergleich: ERSST ist eine **Rekonstruktion** – Lücken im Ozean sind statistisch
aufgefüllt. Über Land wird dagegen nicht interpoliert.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from klima import einlesen
from klima.anomalien import standard_mindestjahre, standard_referenzperiode
from klima.konfiguration import projektwurzel
from klima.weltweit import standard_zellgroesse

GEFRIERPUNKT_MEERWASSER = -1.8
MEEREIS_SCHWELLE = GEFRIERPUNKT_MEERWASSER + 0.01


# --- Landanteil -------------------------------------------------------------------------


def _landanteil_berechnen(groesse: float, unterteilung: int = 20) -> pd.DataFrame:
    """Anteil der Landfläche je Zelle aus Natural Earth, per Stichprobengitter geschätzt."""
    import cartopy.io.shapereader as shpreader
    import shapely

    land = shapely.union_all(
        list(shpreader.Reader(shpreader.natural_earth("50m", "physical", "land")).geometries())
    )
    shapely.prepare(land)

    schritt = groesse / unterteilung
    breiten = np.arange(-90 + schritt / 2, 90, schritt)
    laengen = np.arange(-180 + schritt / 2, 180, schritt)
    gitter_l, gitter_b = np.meshgrid(laengen, breiten)
    ist_land = shapely.contains_xy(land, gitter_l, gitter_b).astype(float)
    gewicht = np.cos(np.deg2rad(gitter_b))  # Stichproben nahe den Polen stehen für weniger Fläche

    form = (len(breiten) // unterteilung, unterteilung, len(laengen) // unterteilung, unterteilung)
    anteil = (ist_land * gewicht).reshape(form).sum(axis=(1, 3)) / gewicht.reshape(form).sum(
        axis=(1, 3)
    )
    mitten_b = -90 + (np.arange(form[0]) + 0.5) * groesse
    mitten_l = -180 + (np.arange(form[2]) + 0.5) * groesse
    lb, ll = np.meshgrid(mitten_b, mitten_l, indexing="ij")
    return pd.DataFrame(
        {"zelle_breite": lb.ravel(), "zelle_laenge": ll.ravel(), "landanteil": anteil.ravel()}
    )


def landanteil(groesse: float | None = None) -> pd.DataFrame:
    """Landanteil (0–1) je Gitterzelle; wird einmalig berechnet und als Parquet gespeichert."""
    groesse = groesse or standard_zellgroesse()
    pfad = (
        projektwurzel() / "daten" / "aufbereitet" / "landmaske" / f"landanteil_{groesse:g}.parquet"
    )
    if pfad.exists():
        return pd.read_parquet(pfad)
    tabelle = _landanteil_berechnen(groesse)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    tabelle.to_parquet(pfad, index=False)
    return tabelle


# --- Ozean ------------------------------------------------------------------------------


def ozeananomalien(
    referenz: tuple[int, int] | None = None,
    groesse: float | None = None,
    mindestjahre: int | None = None,
) -> pd.DataFrame:
    """Monatliche SST-Anomalie je 5°-Zelle aus ERSST: `jahr`, `monat`, `zelle_breite`,
    `zelle_laenge`, `anomalie`, `meerzellen` (Anzahl beitragender 2°-Zellen)."""
    referenz = referenz or standard_referenzperiode()
    groesse = groesse or standard_zellgroesse()
    mindestjahre = standard_mindestjahre() if mindestjahre is None else mindestjahre

    ds = einlesen.ersst()
    sst = ds["sst"].to_numpy().astype(np.float64)  # (zeit, breite, laenge)
    sst[sst <= MEEREIS_SCHWELLE] = np.nan
    zeit = pd.DatetimeIndex(ds["zeit"].to_numpy())
    jahre, monate = zeit.year.to_numpy(), zeit.month.to_numpy()

    # Klimatologie je 2°-Zelle und Kalendermonat
    anomalie = np.full_like(sst, np.nan)
    in_referenz = (jahre >= referenz[0]) & (jahre <= referenz[1])
    for monat in range(1, 13):
        auswahl = monate == monat
        ref = sst[auswahl & in_referenz]
        anzahl = np.isfinite(ref).sum(axis=0)
        with np.errstate(invalid="ignore", divide="ignore"):
            summe_ref = np.nansum(ref, axis=0)
            mittel = np.where(anzahl >= mindestjahre, summe_ref / anzahl, np.nan)
        anomalie[auswahl] = sst[auswahl] - mittel

    # 2°-Zellen den 5°-Zellen zuordnen (Längen 0–358° -> −180–180°)
    breite = ds["breite"].to_numpy().astype(np.float64)
    laenge = ds["laenge"].to_numpy().astype(np.float64)
    laenge = np.where(laenge >= 180, laenge - 360, laenge)
    n_breite, n_laenge = int(180 / groesse), int(360 / groesse)
    zeile = np.clip(((breite + 90) // groesse).astype(int), 0, n_breite - 1)
    spalte = np.clip(((laenge + 180) // groesse).astype(int), 0, n_laenge - 1)
    zelle = (zeile[:, None] * n_laenge + spalte[None, :]).ravel()
    gewicht_quelle = np.repeat(np.cos(np.deg2rad(breite)), len(laenge))

    n_zeit, n_zellen = len(zeit), n_breite * n_laenge
    werte = anomalie.reshape(n_zeit, -1)
    gueltig = np.isfinite(werte)
    gewicht = np.where(gueltig, gewicht_quelle[None, :], 0.0)
    index = (np.arange(n_zeit)[:, None] * n_zellen + zelle[None, :]).ravel()
    summe = np.bincount(
        index, weights=(np.nan_to_num(werte) * gewicht).ravel(), minlength=n_zeit * n_zellen
    )
    gewichte = np.bincount(index, weights=gewicht.ravel(), minlength=n_zeit * n_zellen)
    anzahl = np.bincount(index, weights=gueltig.ravel().astype(float), minlength=n_zeit * n_zellen)

    besetzt = np.flatnonzero(gewichte > 0)
    t, z = np.divmod(besetzt, n_zellen)
    return pd.DataFrame(
        {
            "jahr": jahre[t].astype("int16"),
            "monat": monate[t].astype("int8"),
            "zelle_breite": -90 + (z // n_laenge + 0.5) * groesse,
            "zelle_laenge": -180 + (z % n_laenge + 0.5) * groesse,
            "anomalie": summe[besetzt] / gewichte[besetzt],
            "meerzellen": anzahl[besetzt].astype("int16"),
        }
    )


# --- Kombination ----------------------------------------------------------------------------


def kombinieren(land: pd.DataFrame, ozean: pd.DataFrame, anteil: pd.DataFrame) -> pd.DataFrame:
    """Land- und Ozean-Gitteranomalien je Zelle nach Landanteil gewichten.

    Ergebnis: `jahr`, `monat`, `zelle_breite`, `zelle_laenge`, `anomalie`, `land`, `ozean`,
    `landanteil`.
    """
    schluessel = ["jahr", "monat", "zelle_breite", "zelle_laenge"]
    beide = (
        land[schluessel + ["anomalie"]]
        .rename(columns={"anomalie": "land"})
        .merge(
            ozean[schluessel + ["anomalie"]].rename(columns={"anomalie": "ozean"}),
            on=schluessel,
            how="outer",
        )
    )
    beide = beide.merge(anteil, on=["zelle_breite", "zelle_laenge"], how="left")
    f = beide["landanteil"].fillna(0.0)
    gewichtet = f * beide["land"] + (1 - f) * beide["ozean"]
    beide["anomalie"] = gewichtet.where(
        beide["land"].notna() & beide["ozean"].notna(),
        beide["land"].fillna(beide["ozean"]),
    )
    return beide


def gitterpfad(name: str) -> Path:
    return projektwurzel() / "daten" / "aufbereitet" / "landmaske" / name
