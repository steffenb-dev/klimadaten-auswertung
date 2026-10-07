"""Tests für Aufbereitung (Parquet/NetCDF, Aktualität) und Lade-Schnittstelle."""

from __future__ import annotations

import hashlib

import pytest
from test_parser import GISTEMP_CSV, ghcnm_zeile, schreibe_ghcnm

from klima import einlesen
from klima.aufbereiten import Aufbereitung, RohdatenFehlen, gespeicherte_kennung
from klima.herunterladen import MANIFEST_NAME, Manifest


@pytest.fixture
def projekt(tmp_path, monkeypatch):
    """Leeres Projektverzeichnis; `KLIMA_PROJEKT` zeigt darauf."""
    monkeypatch.setenv("KLIMA_PROJEKT", str(tmp_path))
    (tmp_path / "daten" / "roh").mkdir(parents=True)
    return tmp_path


def registriere(projekt, datensatz: str, relativ: str) -> None:
    """Trägt eine Rohdatei so ins Manifest ein, wie es `klima laden` tun würde."""
    roh = projekt / "daten" / "roh"
    pfad = roh / relativ
    manifest = Manifest(roh / MANIFEST_NAME)
    manifest.setze(
        f"https://beispiel.test/{relativ}",
        {
            "datensatz": datensatz,
            "pfad": relativ,
            "groesse": pfad.stat().st_size,
            "sha256": hashlib.sha256(pfad.read_bytes()).hexdigest(),
        },
    )
    manifest.speichern()


def lege_gistemp_an(projekt, inhalt: str = GISTEMP_CSV) -> None:
    ordner = projekt / "daten" / "roh" / "gistemp"
    ordner.mkdir(exist_ok=True)
    (ordner / "GLB.Ts+dSST.csv").write_text(inhalt)
    registriere(projekt, "gistemp", "gistemp/GLB.Ts+dSST.csv")


def lege_ghcnm_an(projekt) -> None:
    ordner = projekt / "daten" / "roh" / "ghcnm_qcu"
    ordner.mkdir()
    dat = "\n".join(
        [
            ghcnm_zeile("AYM00089606", 1960, [-120] * 12),
            ghcnm_zeile("GM000010147", 1950, [100] * 12, qc="O"),
            ghcnm_zeile("GM000010147", 1990, [200] * 12),
        ]
    )
    schreibe_ghcnm(ordner / "ghcnm.tavg.latest.qcu.tar.gz", dat + "\n")
    registriere(projekt, "ghcnm_qcu", "ghcnm_qcu/ghcnm.tavg.latest.qcu.tar.gz")


def aufbereitung(projekt) -> Aufbereitung:
    return Aufbereitung(projekt / "daten" / "roh", projekt / "daten" / "aufbereitet")


def test_aufbereiten_schreibt_parquet_mit_kennung(projekt):
    lege_gistemp_an(projekt)
    ergebnis = aufbereitung(projekt).aufbereiten("gistemp")
    assert ergebnis.status == "aufbereitet"
    ziel = projekt / "daten" / "aufbereitet" / "gistemp" / "reihen.parquet"
    assert ergebnis.dateien == [ziel]
    assert gespeicherte_kennung(ziel) is not None


def test_zweiter_lauf_ist_aktuell_bis_rohdaten_sich_aendern(projekt):
    lege_gistemp_an(projekt)
    aufbereitung(projekt).aufbereiten("gistemp")
    assert aufbereitung(projekt).aufbereiten("gistemp").status == "aktuell"
    assert aufbereitung(projekt).aufbereiten("gistemp", erzwingen=True).status == "aufbereitet"

    lege_gistemp_an(projekt, GISTEMP_CSV.replace("1.25", "1.30"))  # neue Rohdaten
    assert not aufbereitung(projekt).ist_aktuell("gistemp")
    assert einlesen.gistemp().anomalie.iloc[-1] == pytest.approx(1.30)  # automatisch neu


def test_ohne_rohdaten(projekt):
    assert aufbereitung(projekt).aufbereiten("gistemp").status == "keine_rohdaten"
    with pytest.raises(RohdatenFehlen, match="klima laden gistemp"):
        einlesen.gistemp()


def test_fehlende_rohdatei_trotz_manifest(projekt):
    lege_gistemp_an(projekt)
    (projekt / "daten" / "roh" / "gistemp" / "GLB.Ts+dSST.csv").unlink()
    with pytest.raises(RohdatenFehlen):
        aufbereitung(projekt).aufbereiten("gistemp")


def test_einlesen_ghcnm_mit_filtern(projekt):
    lege_ghcnm_an(projekt)
    stationen = einlesen.ghcnm_stationen("qcu", laender=["GM"])
    assert list(stationen.stations_id) == ["GM000010147"]
    assert "land_name" not in stationen  # Länderliste nicht geladen

    alle = einlesen.ghcnm_monatswerte("qcu", nur_ohne_qc_flag=False)
    assert len(alle) == 36
    # QC-markierter erster Monat von 1950 wird standardmäßig entfernt
    assert len(einlesen.ghcnm_monatswerte("qcu")) == 35

    deutschland = einlesen.ghcnm_monatswerte(
        "qcu", stationen=stationen.stations_id, von=1980, spalten=["jahr", "tavg"]
    )
    assert list(deutschland.columns) == ["jahr", "tavg"]
    assert len(deutschland) == 12
    assert set(deutschland.jahr) == {1990}


def test_einlesen_unbekannte_variante(projekt):
    with pytest.raises(ValueError, match="Variante"):
        einlesen.ghcnm_monatswerte("xyz")
