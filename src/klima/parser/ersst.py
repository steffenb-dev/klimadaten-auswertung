"""Parser für ERSST v5: fügt die monatlichen NetCDF-Dateien zu einem `xarray.Dataset` zusammen.

Jede Rohdatei (`ersst.v5.JJJJMM.nc`) enthält ein 2°×2°-Gitter (89 Breiten × 180 Längen)
mit der Meeresoberflächentemperatur `sst` in °C. Landzellen und Meereis ohne Wert sind NaN.
"""

from __future__ import annotations

import re
from pathlib import Path

import netCDF4
import numpy as np
import pandas as pd
import xarray as xr

DATEIMUSTER = re.compile(r"ersst\.v5\.(\d{4})(\d{2})\.nc")


def _monat_aus_name(pfad: Path) -> pd.Timestamp:
    treffer = DATEIMUSTER.fullmatch(pfad.name)
    if not treffer:
        raise ValueError(f"Unerwarteter ERSST-Dateiname: {pfad.name}")
    return pd.Timestamp(year=int(treffer[1]), month=int(treffer[2]), day=1)


def lies_ersst(dateien: list[Path]) -> xr.Dataset:
    """Liest die Monatsdateien und gibt ein Dataset mit `sst(zeit, breite, laenge)` zurück.

    `zeit` ist jeweils der Monatserste. Die Reihenfolge der Dateien ist beliebig.
    """
    if not dateien:
        raise ValueError("Keine ERSST-Dateien angegeben.")
    dateien = sorted(dateien, key=_monat_aus_name)
    zeiten = pd.DatetimeIndex([_monat_aus_name(p) for p in dateien])
    if zeiten.has_duplicates:
        raise ValueError("Doppelte ERSST-Monate.")

    with netCDF4.Dataset(dateien[0]) as erste:
        breite = np.asarray(erste["lat"][:], dtype=np.float32)
        laenge = np.asarray(erste["lon"][:], dtype=np.float32)
        einheit = erste["sst"].getncattr("units") if "units" in erste["sst"].ncattrs() else ""

    sst = np.empty((len(dateien), len(breite), len(laenge)), dtype=np.float32)
    for i, pfad in enumerate(dateien):
        with netCDF4.Dataset(pfad) as nc:
            variable = nc["sst"]
            variable.set_auto_maskandscale(True)
            gitter = variable[0, 0, :, :]  # (time, lev, lat, lon) -> (lat, lon)
            if gitter.shape != sst.shape[1:]:
                raise ValueError(f"{pfad.name}: abweichende Gittergröße {gitter.shape}")
            sst[i] = np.ma.filled(gitter.astype(np.float32), np.nan)

    return xr.Dataset(
        {"sst": (("zeit", "breite", "laenge"), sst, {"einheit": einheit or "degree_C"})},
        coords={
            "zeit": zeiten,
            "breite": ("breite", breite, {"einheit": "degrees_north"}),
            "laenge": ("laenge", laenge, {"einheit": "degrees_east (0–358)"}),
        },
        attrs={
            "titel": "NOAA ERSST v5, Meeresoberflächentemperatur",
            "quelle": "https://www.ncei.noaa.gov/pub/data/cmb/ersst/v5/netcdf/",
        },
    )
