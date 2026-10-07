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
