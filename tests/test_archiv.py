"""Tests für das Lesen aus Archiven im Arbeitsspeicher."""

from __future__ import annotations

import gzip
import io
import tarfile
import zipfile

import pytest

from klima.archiv import finde, inhalt, ist_archiv, lies, oeffne_text

DAT = b"ACW00011604 1961TAVG -142  k  -81  k\nGM000010147 1990TAVG  120     150   \n"
INV = b"GM000010147  53.6331    9.9881   11.0 HAMBURG_FUHLSBUETTEL\n"


@pytest.fixture
def tar_gz(tmp_path):
    pfad = tmp_path / "ghcnm.tavg.latest.qcu.tar.gz"
    with tarfile.open(pfad, "w:gz") as archiv:
        for name, inhalt_ in {
            "ghcnm.v4.0.1.20261006/ghcnm.tavg.v4.0.1.20261006.qcu.dat": DAT,
            "ghcnm.v4.0.1.20261006/ghcnm.tavg.v4.0.1.20261006.qcu.inv": INV,
        }.items():
            info = tarfile.TarInfo(name)
            info.size = len(inhalt_)
            archiv.addfile(info, io.BytesIO(inhalt_))
    return pfad


@pytest.fixture
def zip_datei(tmp_path):
    pfad = tmp_path / "tageswerte_KL_00044_akt.zip"
    with zipfile.ZipFile(pfad, "w") as archiv:
        archiv.writestr("produkt_klima_tag_20250101_20261006_00044.txt", "STATIONS_ID;MESS_DATUM\n")
        archiv.writestr("Metadaten_Geographie_00044.txt", "Stations_id;Stationshoehe\n")
    return pfad


def test_tar_inhalt_und_suche(tar_gz):
    assert len(inhalt(tar_gz)) == 2
    assert finde(tar_gz, "*.inv") == ["ghcnm.v4.0.1.20261006/ghcnm.tavg.v4.0.1.20261006.qcu.inv"]


def test_tar_datei_zeilenweise_lesen(tar_gz):
    with oeffne_text(tar_gz, "*.qcu.dat") as datei:
        zeilen = list(datei)
    assert len(zeilen) == 2
    assert zeilen[1].startswith("GM000010147 1990")


def test_zip_lesen(zip_datei):
    assert lies(zip_datei, "produkt_klima_tag_*").startswith(b"STATIONS_ID")


def test_gz_einzeldatei(tmp_path):
    pfad = tmp_path / "2024.csv.gz"
    pfad.write_bytes(gzip.compress(b"ID,DATUM\n"))
    assert inhalt(pfad) == ["2024.csv"]
    assert lies(pfad) == b"ID,DATUM\n"


def test_unkomprimierte_datei(tmp_path):
    pfad = tmp_path / "GLB.Ts.csv"
    pfad.write_text("Year,Jan\n")
    assert not ist_archiv(pfad)
    with oeffne_text(pfad) as datei:
        assert datei.read() == "Year,Jan\n"


def test_mehrdeutiges_oder_fehlendes_muster(tar_gz):
    with pytest.raises(FileNotFoundError, match="2 Dateien"):
        lies(tar_gz)
    with pytest.raises(FileNotFoundError, match="0 Treffer"):
        lies(tar_gz, "*.csv")


def test_nichts_wird_auf_die_festplatte_entpackt(tar_gz, zip_datei, tmp_path):
    vorher = sorted(p.name for p in tmp_path.rglob("*"))
    lies(tar_gz, "*.dat")
    lies(zip_datei, "Metadaten_*")
    assert sorted(p.name for p in tmp_path.rglob("*")) == vorher
