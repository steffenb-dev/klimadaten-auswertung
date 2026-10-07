"""Tests der Parser mit kleinen, künstlichen Rohdateien im Originalformat."""

from __future__ import annotations

import io
import tarfile

import netCDF4
import numpy as np
import pytest

from klima.parser import dwd, ersst, ghcnm, vergleichsreihen

FEHLT = -9999


def ghcnm_zeile(stations_id: str, jahr: int, werte: list[int], qc: str = " ") -> str:
    """Eine `.dat`-Zeile; DS-Flag ist immer `k`, QC-Flag optional für den ersten Monat."""
    monate = [f"{w:5d} {qc if i == 0 else ' '}k" for i, w in enumerate(werte)]
    zeile = f"{stations_id:<11}{jahr:4d}TAVG" + "".join(monate)
    assert len(zeile) == ghcnm.ZEILENLAENGE
    return zeile


INV = (
    "GM000010147  53.6331    9.9881   11.0 HAMBURG_FUHLSBUETTEL          \n"
    "AYM00089606 -66.2830  110.5170 -999.0 CASEY                         \n"
)


def schreibe_ghcnm(pfad, dat: str) -> None:
    with tarfile.open(pfad, "w:gz") as archiv:
        for name, inhalt in {"ghcnm.v4/x.qcu.dat": dat, "ghcnm.v4/x.qcu.inv": INV}.items():
            daten = inhalt.encode("latin-1")
            info = tarfile.TarInfo(name)
            info.size = len(daten)
            archiv.addfile(info, io.BytesIO(daten))


@pytest.fixture
def ghcnm_archiv(tmp_path):
    hamburg_1990 = [50, 120, 410, 820, 1250, 1500, 1720, 1680, 1390, 950, 520, 150]
    dat = "\n".join(
        [
            ghcnm_zeile("AYM00089606", 1990, [-120] * 11 + [FEHLT]),
            ghcnm_zeile("GM000010147", 1950, [FEHLT] * 12),
            ghcnm_zeile("GM000010147", 1990, hamburg_1990, qc="O"),
            ghcnm_zeile("GM000010147", 2020, [-5] + [FEHLT] * 11),
        ]
    )  # letzte Zeile bewusst ohne Zeilenumbruch
    pfad = tmp_path / "ghcnm.tar.gz"
    schreibe_ghcnm(pfad, dat)
    return pfad


def test_ghcnm_stationen(ghcnm_archiv):
    stationen = ghcnm.lies_stationen(ghcnm_archiv)
    assert list(stationen.stations_id) == ["GM000010147", "AYM00089606"]
    assert list(stationen.land) == ["GM", "AY"]
    assert stationen.loc[0, "name"] == "HAMBURG_FUHLSBUETTEL"
    assert stationen.loc[0, "breite"] == pytest.approx(53.6331)
    assert np.isnan(stationen.loc[1, "hoehe"])  # -999.0 = fehlend


def test_ghcnm_monatswerte(ghcnm_archiv):
    werte = ghcnm.lies_monatswerte(ghcnm_archiv)
    # 11 (Casey) + 0 (1950 komplett fehlend) + 12 + 1
    assert len(werte) == 24
    hamburg = werte[(werte.stations_id == "GM000010147") & (werte.jahr == 1990)]
    assert list(hamburg.monat) == list(range(1, 13))
    assert hamburg.tavg.iloc[6] == pytest.approx(17.2)
    assert hamburg.qc_flag.iloc[0] == "O"
    assert hamburg.qc_flag.iloc[1:].isna().all()
    assert (werte.ds_flag == "k").all()
    assert werte.tavg.dtype == np.float32


def test_ghcnm_filter_beim_lesen(ghcnm_archiv):
    werte = ghcnm.lies_monatswerte(ghcnm_archiv, stationen=["GM000010147"], von_jahr=2000)
    assert len(werte) == 1
    assert werte.iloc[0].tavg == pytest.approx(-0.05)


def test_ghcnm_falsche_zeilenlaenge(tmp_path):
    pfad = tmp_path / "kaputt.tar.gz"
    schreibe_ghcnm(pfad, ghcnm_zeile("GM000010147", 1990, [0] * 12) + "\nzu kurz\n")
    with pytest.raises(ValueError):
        ghcnm.lies_monatswerte(pfad)


def test_ghcnm_laender(tmp_path):
    pfad = tmp_path / "ghcnm-countries.txt"
    pfad.write_text("AC Antigua and Barbuda \nGM Germany\n")
    laender = ghcnm.lies_laender(pfad)
    assert laender.to_dict("list") == {
        "land": ["AC", "GM"],
        "land_name": ["Antigua and Barbuda", "Germany"],
    }


# --- ERSST -----------------------------------------------------------------------


def schreibe_ersst(pfad, wert: float) -> None:
    with netCDF4.Dataset(pfad, "w") as nc:
        for dim, n in (("time", 1), ("lev", 1), ("lat", 3), ("lon", 4)):
            nc.createDimension(dim, n)
        nc.createVariable("lat", "f8", ("lat",))[:] = [-2.0, 0.0, 2.0]
        nc.createVariable("lon", "f8", ("lon",))[:] = [0.0, 2.0, 4.0, 6.0]
        sst = nc.createVariable("sst", "f4", ("time", "lev", "lat", "lon"), fill_value=-999.0)
        sst.units = "degree_C"
        daten = np.full((1, 1, 3, 4), wert, dtype=np.float32)
        daten[0, 0, 1, 1] = -999.0  # Landzelle
        sst[0, 0, :, :] = daten[0, 0]


def test_ersst(tmp_path):
    dateien = []
    for monat, wert in ((2, 11.0), (1, 10.0)):  # absichtlich unsortiert
        pfad = tmp_path / f"ersst.v5.2024{monat:02d}.nc"
        schreibe_ersst(pfad, wert)
        dateien.append(pfad)

    ds = ersst.lies_ersst(dateien)
    assert dict(ds.sizes) == {"zeit": 2, "breite": 3, "laenge": 4}
    assert str(ds.zeit.values[0])[:10] == "2024-01-01"
    assert float(ds.sst.isel(zeit=0, breite=0, laenge=0)) == 10.0
    assert np.isnan(ds.sst.isel(zeit=1, breite=1, laenge=1))


# --- GISTEMP ---------------------------------------------------------------------

GISTEMP_CSV = """Land-Ocean: Global Means
Year,Jan,Feb,Mar,Apr,May,Jun,Jul,Aug,Sep,Oct,Nov,Dec,J-D,D-N,DJF,MAM,JJA,SON
1880,-.19,-.26,-.10,-.17,-.11,-.22,-.19,-.11,-.15,-.24,-.23,-.18,-.18,***,***,-.13,-.17,-.21
2026,1.09,1.25,***,***,***,***,***,***,***,***,***,***,***,***,1.13,***,***,***
"""


def test_gistemp(tmp_path):
    pfad = tmp_path / "GLB.Ts+dSST.csv"
    pfad.write_text(GISTEMP_CSV)
    reihe = vergleichsreihen.lies_gistemp(pfad)
    assert len(reihe) == 14
    assert set(reihe.gebiet) == {"global"} and set(reihe.art) == {"land_ozean"}
    letzte = reihe.iloc[-1]
    assert (letzte.jahr, letzte.monat) == (2026, 2)
    assert letzte.anomalie == pytest.approx(1.25)


def test_gistemp_unbekannte_datei(tmp_path):
    pfad = tmp_path / "XYZ.csv"
    pfad.write_text(GISTEMP_CSV)
    with pytest.raises(ValueError):
        vergleichsreihen.lies_gistemp(pfad)


# --- DWD -------------------------------------------------------------------------

DWD_STATIONEN = (
    "Stations_id von_datum bis_datum Stationshoehe geoBreite geoLaenge Stationsname "
    "Bundesland Abgabe\r\n"
    "----------- --------- --------- ------------- --------- --------- "
    "----------------------------------------- ---------- ------\r\n"
    "00001 19310101 19860630            478     47.8413    8.8493 Aach"
    + " " * 37
    + "Baden-Württemberg"
    + " " * 24
    + "Frei   \r\n"
    "20318 19370801 19601231            352     48.7726    8.7287 Liebenzell, Bad/ Nagold"
    + " " * 18
    + "Baden-Württemberg"
    + " " * 24
    + "       \r\n"
)


def test_dwd_stationsliste(tmp_path):
    pfad = tmp_path / "KL_Monatswerte_Beschreibung_Stationen.txt"
    pfad.write_bytes(DWD_STATIONEN.encode("latin-1"))
    stationen = dwd.lies_stationsliste(pfad)
    assert list(stationen.stations_id) == ["00001", "20318"]
    assert list(stationen.name) == ["Aach", "Liebenzell, Bad/ Nagold"]
    assert list(stationen.bundesland) == ["Baden-Württemberg"] * 2
    assert list(stationen.abgabe) == ["Frei", ""]
    assert str(stationen.von.iloc[0].date()) == "1931-01-01"
    assert stationen.hoehe.iloc[0] == 478


DWD_GEBIETSMITTEL = (
    "Zeitreihen fuer Gebietsmittel, erstellt am: 20261002\n"
    "Jahr;Monat;Bayern;Deutschland;\n"
    "1881;01;    -6.51;    -5.36;\n"
    "1882;01;  -999;     0.41;\n"
)


def test_dwd_gebietsmittel(tmp_path):
    pfad = tmp_path / "regional_averages_tm_01.txt"
    pfad.write_text(DWD_GEBIETSMITTEL, encoding="latin-1")
    werte = dwd.lies_gebietsmittel(pfad, "temperatur")
    assert list(werte.columns) == ["gebiet", "jahr", "monat", "temperatur"]
    assert len(werte) == 3  # Fehlwert -999 entfernt
    deutschland = werte[werte.gebiet == "Deutschland"]
    assert list(deutschland.temperatur) == pytest.approx([-5.36, 0.41])
