"""Tests für die globale Auswertung (Halbkugeln, Abdeckung, Jahrzehnte, Stationstrends)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from test_aufbereiten import lege_ghcnm_an, projekt  # noqa: F401 (Fixture)

from klima import weltweit as ww


def gitter_aus(zellen: list[tuple[float, float, float]], jahre=(2000,)) -> pd.DataFrame:
    """Gitter mit gleicher Anomalie in allen Monaten der angegebenen Jahre."""
    zeilen = [
        (jahr, monat, b, lg, wert, 1)
        for jahr in jahre
        for monat in range(1, 13)
        for b, lg, wert in zellen
    ]
    return pd.DataFrame(
        zeilen, columns=["jahr", "monat", "zelle_breite", "zelle_laenge", "anomalie", "stationen"]
    )


def test_halbkugeln_und_halbkugelmittel():
    # Norden: viele Zellen mit +1, Süden: eine Zelle mit 0 -> global nordlastig
    gitter = gitter_aus([(52.5, lg, 1.0) for lg in (2.5, 7.5, 12.5)] + [(-32.5, 2.5, 0.0)])
    jahre = ww.jahresanomalien(gitter).iloc[0]
    assert jahre["nordhalbkugel"] == pytest.approx(1.0)
    assert jahre["suedhalbkugel"] == pytest.approx(0.0)
    assert jahre["halbkugelmittel"] == pytest.approx(0.5)
    assert 0.5 < jahre["global"] < 1.0


def test_unvollstaendige_jahre_fehlen():
    gitter = gitter_aus([(2.5, 2.5, 1.0)])
    gitter = gitter[gitter["monat"] != 7]
    assert ww.jahresanomalien(gitter, gebiete=("global",)).empty


def test_abdeckung_flaechenanteil():
    # Alle 72 Zellen eines 5°-Breitenbands am Äquator nördlich und südlich (-5° bis +5°)
    zellen = [(b, lg, 0.0) for b in (-2.5, 2.5) for lg in np.arange(-177.5, 180, 5.0)]
    gitter = gitter_aus(zellen)
    stationen = pd.DataFrame({"jahr": [2000, 2000], "stations_id": ["a", "b"]})
    abdeckung = ww.abdeckung(gitter, stationen, groesse=5.0).iloc[0]
    # Anteil der Kugeloberfläche zwischen -5° und +5° = sin(5°)
    assert abdeckung["flaechenanteil"] == pytest.approx(np.sin(np.deg2rad(5)) * 100)
    assert (abdeckung["stationen"], abdeckung["zellen"]) == (2, 144)


def test_jahrzehntmittel():
    gitter = gitter_aus([(52.5, 7.5, 1.0)], jahre=range(2010, 2016))
    gitter.loc[gitter["jahr"] == 2015, "anomalie"] = 2.0
    mittel = ww.jahrzehntmittel(gitter, mindestmonate=60)
    assert list(mittel["jahrzehnt"]) == [2010]
    assert mittel["anomalie"].iloc[0] == pytest.approx((5 * 1 + 2) / 6)
    assert ww.jahrzehntmittel(gitter, mindestmonate=73).empty


def test_stationstrends_vektorisiert(projekt):  # noqa: F811
    lege_ghcnm_an(projekt)  # Hamburg: 1950 mit 1 °C, 1990 mit 2 °C; Casey nur 1960
    trends = ww.stationstrends("qcu", von=1950, bis=1990, mindestanteil=0.0)
    hamburg = trends.set_index("stations_id").loc["GM000010147"]
    # 1950 ist wegen QC-Flag im Januar unvollständig -> nur 1990 -> Steigung nicht bestimmbar
    assert hamburg["jahre"] == 1
    assert np.isnan(hamburg["trend"])
