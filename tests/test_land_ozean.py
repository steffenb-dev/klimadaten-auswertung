"""Tests für Ozeananomalien, Landanteil, Kombination Land/Ozean und HadCRUT5."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from klima import land_ozean as lo
from klima.parser import vergleichsreihen


def ersst_kuenstlich(jahre=range(1951, 1991)) -> xr.Dataset:
    """2°-Gitter: überall 15 °C + 0,02 °C/Jahr, zwei Zellen unter Meereis (−1,8 °C)."""
    zeit = pd.date_range(f"{jahre[0]}-01-01", f"{jahre[-1]}-12-01", freq="MS")
    breite = np.arange(-88.0, 90.0, 2.0)
    laenge = np.arange(0.0, 360.0, 2.0)
    werte = 15 + 0.02 * (zeit.year.to_numpy() - 1951)
    sst = np.broadcast_to(werte[:, None, None], (len(zeit), len(breite), len(laenge))).copy()
    sst[:, -1, :2] = lo.GEFRIERPUNKT_MEERWASSER  # Meereis bei 88° N
    return xr.Dataset(
        {"sst": (("zeit", "breite", "laenge"), sst.astype(np.float32))},
        coords={"zeit": zeit, "breite": breite, "laenge": laenge},
    )


def test_ozeananomalien(monkeypatch):
    monkeypatch.setattr(lo.einlesen, "ersst", lambda: ersst_kuenstlich())
    ozean = lo.ozeananomalien(referenz=(1951, 1980), groesse=5.0, mindestjahre=20)
    # Anomalie 1990 = 0,02 × (1990 − 1965,5)
    werte_1990 = ozean[ozean["jahr"] == 1990]["anomalie"]
    assert werte_1990.to_numpy() == pytest.approx(0.02 * (1990 - 1965.5), abs=1e-6)
    # Längen werden auf −180 … 180 umgerechnet, alle 5°-Zellen sind besetzt (36 × 72)
    assert ozean["zelle_laenge"].between(-180, 180).all()
    assert ozean[(ozean["jahr"] == 1990) & (ozean["monat"] == 1)].shape[0] == 36 * 72
    # Die Zelle mit Meereis hat weniger beitragende 2°-Zellen
    polar = ozean[(ozean["zelle_breite"] == 87.5) & (ozean["zelle_laenge"] == 2.5)]
    normal = ozean[(ozean["zelle_breite"] == 82.5) & (ozean["zelle_laenge"] == 2.5)]
    assert polar["meerzellen"].iloc[0] < normal["meerzellen"].iloc[0]


def test_kombinieren_nach_landanteil():
    schluessel = {"jahr": [2000], "monat": [1], "zelle_breite": [52.5], "zelle_laenge": [7.5]}
    land = pd.DataFrame({**schluessel, "anomalie": [2.0]})
    ozean = pd.DataFrame({**schluessel, "anomalie": [1.0]})
    anteil = pd.DataFrame({"zelle_breite": [52.5], "zelle_laenge": [7.5], "landanteil": [0.75]})
    ergebnis = lo.kombinieren(land, ozean, anteil)
    assert ergebnis["anomalie"].iloc[0] == pytest.approx(0.75 * 2 + 0.25 * 1)


def test_kombinieren_nur_ein_wert():
    land = pd.DataFrame({"jahr": [2000], "monat": [1], "zelle_breite": [2.5],
                         "zelle_laenge": [2.5], "anomalie": [3.0]})  # fmt: skip
    ozean = pd.DataFrame({"jahr": [2000], "monat": [1], "zelle_breite": [-2.5],
                          "zelle_laenge": [2.5], "anomalie": [0.5]})  # fmt: skip
    anteil = pd.DataFrame({"zelle_breite": [2.5, -2.5], "zelle_laenge": [2.5, 2.5],
                           "landanteil": [0.1, 0.9]})  # fmt: skip
    ergebnis = lo.kombinieren(land, ozean, anteil).set_index("zelle_breite")
    # Liegt nur ein Wert vor, wird er unabhängig vom Landanteil verwendet
    assert ergebnis.loc[2.5, "anomalie"] == pytest.approx(3.0)
    assert ergebnis.loc[-2.5, "anomalie"] == pytest.approx(0.5)


def test_landanteil_der_erde():
    pytest.importorskip("shapely")
    try:
        anteil = lo._landanteil_berechnen(groesse=30.0, unterteilung=30)
    except Exception as fehler:  # Natural Earth nicht verfügbar (kein Netz, kein Cache)
        pytest.skip(f"Landmaske nicht verfügbar: {fehler}")
    gewicht = np.cos(np.deg2rad(anteil["zelle_breite"]))
    gesamt = (anteil["landanteil"] * gewicht).sum() / gewicht.sum()
    assert gesamt == pytest.approx(0.29, abs=0.02)  # ~29 % der Erdoberfläche ist Land
    assert anteil["landanteil"].between(0, 1).all()


def test_hadcrut_parser(tmp_path):
    pfad = tmp_path / "HadCRUT.5.2.0.0.noninfilled.summary_series.northern_hemisphere.annual.csv"
    pfad.write_text(
        "Time,Anomaly (deg C),Lower confidence limit (2.5%),Upper confidence limit (97.5%)\n"
        "1850,-0.35,-0.62,-0.09\n2025,1.00,0.92,1.08\n"
    )
    reihe = vergleichsreihen.lies_hadcrut(pfad)
    assert set(reihe["gebiet"]) == {"nordhalbkugel"}
    assert set(reihe["variante"]) == {"nicht_aufgefuellt"}
    assert list(reihe["jahr"]) == [1850, 2025]
    assert reihe["oben"].iloc[1] == pytest.approx(1.08)
    with pytest.raises(ValueError):
        vergleichsreihen.lies_hadcrut(tmp_path / "irgendwas.csv")
