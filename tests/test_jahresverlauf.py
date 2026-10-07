"""Tests für den 365-Tage-Kalender, die Tagesklimatologie und den DWD-Tageswerte-Parser."""

from __future__ import annotations

import zipfile

import numpy as np
import pandas as pd
import pytest

from klima.jahresverlauf import (
    SCHALTTAG,
    _zirkulaer_glaetten,
    jahresmatrix,
    tag_im_jahr,
    tagesklimatologie,
    vollstaendige_jahre,
)
from klima.parser import dwd


def test_tag_im_jahr_365_tage_kalender():
    daten = pd.Series(
        pd.to_datetime(
            ["2023-01-01", "2023-03-01", "2023-12-31", "2024-02-28", "2024-02-29",
             "2024-03-01", "2024-12-31"]
        )
    )  # fmt: skip
    # 1. März ist in jedem Jahr Tag 60, 31.12. immer Tag 365, 29.02. wird markiert
    assert list(tag_im_jahr(daten)) == [1, 60, 365, 59, SCHALTTAG, 60, 365]


def test_zirkulaeres_glaetten_ueber_den_jahreswechsel():
    zeile = np.zeros((1, 365))
    zeile[0, 0] = 365.0  # 1. Januar
    geglaettet = _zirkulaer_glaetten(zeile, fenster=5, mindestanteil=1.0)
    # Das Fenster um den 31.12. (Tag 365) enthält den 1.1. -> Mittel 365/5
    assert geglaettet[0, 364] == pytest.approx(73.0)
    assert geglaettet[0, 2] == pytest.approx(73.0)
    assert geglaettet[0, 3] == pytest.approx(0.0)


def test_tagesklimatologie_braucht_genug_jahre():
    tage = pd.date_range("1951-01-01", "1980-12-31")
    werte = pd.DataFrame({"stations_id": "a", "datum": tage, "jahr": tage.year, "t": 5.0})
    werte["tag"] = tag_im_jahr(werte["datum"])
    stationen, klima = tagesklimatologie(werte, "t", (1951, 1980), mindestjahre=20)
    assert list(stationen) == ["a"]
    assert klima.shape == (1, 365)
    np.testing.assert_allclose(klima, 5.0)
    _, zu_wenig = tagesklimatologie(werte, "t", (1951, 1980), mindestjahre=31)
    assert zu_wenig.shape[0] == 0


def test_jahresmatrix_und_vollstaendige_jahre():
    tage = pd.date_range("2023-01-01", "2024-06-30")
    tagesmittel = pd.DataFrame(
        {"datum": tage, "jahr": tage.year, "tmittel": np.arange(len(tage), dtype=float),
         "zellen": 20}
    )  # fmt: skip
    tagesmittel["tag"] = tag_im_jahr(tagesmittel["datum"])
    matrix = jahresmatrix(tagesmittel)
    assert matrix.shape == (2, 365)
    assert matrix.loc[2024].isna().sum() == 365 - 181  # bis 30.06. ohne 29.02.
    assert vollstaendige_jahre(tagesmittel, mindestzellen=15) == [2023]
    assert vollstaendige_jahre(tagesmittel, mindestzellen=25) == []


def test_dwd_tageswerte_parser(tmp_path):
    produkt = (
        "STATIONS_ID;MESS_DATUM;QN_3;  FX;  FM;QN_4; RSK;RSKF; SDK;SHK_TAG;  NM; VPM;  PM; TMK;"
        " UPM; TXK; TNK; TGK;eor\n"
        "       3987;20250405;   10;  14.9;   4.6;    9;   0.0;   7;    9.500;   0;   4.8;"
        "   5.6; 1008.00;    7.2;   56.00;   12.4;   -0.1;   -3.9;eor\n"
        "       3987;20250406;   10;  11.7;   3.6;    9;-999;   0;    9.600;   0;   3.6;"
        "   4.1; 1014.30;    4.0;   53.00;   10.0;   -1.0;   -4.8;eor\n"
    )
    hist = tmp_path / "tageswerte_KL_03987_18930101_20250405_hist.zip"
    akt = tmp_path / "tageswerte_KL_03987_akt.zip"
    for pfad, name in ((hist, "produkt_klima_tag_x.txt"), (akt, "produkt_klima_zug_tag_y.txt")):
        with zipfile.ZipFile(pfad, "w") as archiv:
            archiv.writestr(name, produkt.replace("7.2", "7.2" if pfad is hist else "9.9"))
            archiv.writestr("Metadaten_Geographie_03987.txt", "x")

    werte = dwd.lies_tageswerte_alle([akt, hist])
    assert list(werte.datum.dt.strftime("%Y-%m-%d")) == ["2025-04-05", "2025-04-06"]
    # Überschneidung: historischer (geprüfter) Wert hat Vorrang
    assert werte.tmittel.iloc[0] == pytest.approx(7.2)
    assert np.isnan(werte.niederschlag.iloc[1])  # -999 = fehlend
    assert werte.tmax.iloc[0] == pytest.approx(12.4)
    assert list(werte.jahr) == [2025, 2025]
