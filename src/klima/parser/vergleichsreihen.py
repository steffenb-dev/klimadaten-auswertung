"""Parser für fertige Vergleichsreihen der Wissenschaft (NASA GISTEMP v4)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from klima.archiv import oeffne_text

MONATE = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# Dateiname -> (Gebiet, Art)
GISTEMP_REIHEN = {
    "GLB.Ts+dSST.csv": ("global", "land_ozean"),
    "NH.Ts+dSST.csv": ("nordhalbkugel", "land_ozean"),
    "SH.Ts+dSST.csv": ("suedhalbkugel", "land_ozean"),
    "GLB.Ts.csv": ("global", "land"),
    "NH.Ts.csv": ("nordhalbkugel", "land"),
    "SH.Ts.csv": ("suedhalbkugel", "land"),
}


def lies_gistemp(pfad: Path) -> pd.DataFrame:
    """Eine GISTEMP-Tabelle als Long-Format: `gebiet`, `art`, `jahr`, `monat`, `anomalie` (°C).

    Anomalien beziehen sich auf 1951–1980. Fehlende Monate (`***`) werden entfernt.
    """
    if pfad.name not in GISTEMP_REIHEN:
        raise ValueError(f"Unbekannte GISTEMP-Reihe: {pfad.name}")
    gebiet, art = GISTEMP_REIHEN[pfad.name]

    with oeffne_text(pfad) as datei:
        tabelle = pd.read_csv(datei, skiprows=1, na_values=["***", "****"])
    lang = tabelle.melt(id_vars="Year", value_vars=MONATE, var_name="monat", value_name="anomalie")
    lang = lang.dropna(subset=["anomalie"])
    lang["monat"] = lang["monat"].map({m: i for i, m in enumerate(MONATE, start=1)})
    lang = lang.rename(columns={"Year": "jahr"}).sort_values(["jahr", "monat"])
    lang.insert(0, "gebiet", gebiet)
    lang.insert(1, "art", art)
    return lang.astype({"jahr": "int16", "monat": "int8", "anomalie": "float32"}).reset_index(
        drop=True
    )


def lies_gistemp_alle(dateien: list[Path]) -> pd.DataFrame:
    """Alle GISTEMP-Reihen in einer Tabelle, Gebiet und Art als Kategorien."""
    teile = [lies_gistemp(p) for p in sorted(dateien)]
    alle = pd.concat(teile, ignore_index=True)
    return alle.astype({"gebiet": "category", "art": "category"})


# --- HadCRUT5 (Met Office / UEA CRU) -------------------------------------------------

HADCRUT_GEBIETE = {
    "global": "global",
    "northern_hemisphere": "nordhalbkugel",
    "southern_hemisphere": "suedhalbkugel",
}
HADCRUT_VARIANTEN = {"analysis": "aufgefuellt", "noninfilled": "nicht_aufgefuellt"}
HADCRUT_REFERENZ = (1961, 1990)


def lies_hadcrut(pfad: Path) -> pd.DataFrame:
    """Eine HadCRUT5-Jahresreihe: `gebiet`, `variante`, `jahr`, `anomalie`, `unten`, `oben`.

    Anomalien beziehen sich auf 1961–1990; `unten`/`oben` sind die Grenzen des
    95-%-Unsicherheitsbereichs. Das laufende Jahr ist in der Quelle bereits enthalten
    (Mittel der bisherigen Monate).
    """
    teile = pfad.name.split(".")
    try:
        variante = HADCRUT_VARIANTEN[teile[5]]
        gebiet = HADCRUT_GEBIETE[teile[7]]
    except (IndexError, KeyError) as fehler:
        raise ValueError(f"Unbekannte HadCRUT-Datei: {pfad.name}") from fehler
    with oeffne_text(pfad) as datei:
        tabelle = pd.read_csv(datei)
    tabelle.columns = ["jahr", "anomalie", "unten", "oben"]
    tabelle.insert(0, "gebiet", gebiet)
    tabelle.insert(1, "variante", variante)
    return tabelle.astype({"jahr": "int16", "anomalie": "float32", "unten": "float32",
                           "oben": "float32"})  # fmt: skip


def lies_hadcrut_alle(dateien: list[Path]) -> pd.DataFrame:
    alle = pd.concat([lies_hadcrut(p) for p in sorted(dateien)], ignore_index=True)
    return alle.astype({"gebiet": "category", "variante": "category"})
