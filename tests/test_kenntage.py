"""Tests für Kenntage, Niederschlagsindizes, GHCN-Daily und den Typ Stationsauswahl."""

from __future__ import annotations

import gzip

import httpx
import numpy as np
import pandas as pd
import pytest

from klima.herunterladen import Zeitraum, dateien_ermitteln
from klima.kenntage import laeufe, tage_im_jahr, temperaturindizes
from klima.konfiguration import _datensatz_aus_eintrag
from klima.niederschlag import _summe_mehrtaegig, niederschlagsindizes
from klima.parser import dwd, ghcnd

SCHWELLEN = {
    "sommertag_tmax": 25.0, "heisser_tag_tmax": 30.0, "tropennacht_tmin": 20.0,
    "frosttag_tmin": 0.0, "eistag_tmax": 0.0, "hitzewelle_mindesttage": 3,
    "mindestanteil_tage": 0.9,
}  # fmt: skip


def jahr_tageswerte(jahr: int = 2001, station: str = "a", **spalten) -> pd.DataFrame:
    datum = pd.date_range(f"{jahr}-01-01", f"{jahr}-12-31")
    tabelle = pd.DataFrame({"stations_id": station, "datum": datum, "jahr": datum.year})
    for name, wert in spalten.items():
        tabelle[name] = wert
    return tabelle


def test_tage_im_jahr():
    assert list(tage_im_jahr([1900, 2000, 2023, 2024])) == [365, 366, 365, 366]


def test_laeufe_beachten_luecken_und_stationen():
    tabelle = pd.DataFrame(
        {
            "stations_id": ["a"] * 6 + ["b"] * 2,
            "datum": pd.to_datetime(
                [
                    "2001-07-01",
                    "2001-07-02",
                    "2001-07-03",
                    "2001-07-05",
                    "2001-07-06",
                    "2001-07-07",
                    "2001-07-08",
                    "2001-07-09",
                ]
            ),  # fmt: skip
            "jahr": 2001,
        }
    )
    bedingung = np.array([True, True, True, True, True, False, True, True])
    ergebnis = laeufe(tabelle, bedingung)
    # 01.–03.07. (3 Tage), Lücke am 04.07., dann 05.–06.07. (2 Tage), Station b: 2 Tage
    assert sorted(ergebnis["laenge"]) == [2, 2, 3]
    assert set(ergebnis["stations_id"]) == {"a", "b"}


def test_temperaturindizes():
    tabelle = jahr_tageswerte(tmax=10.0, tmin=2.0)
    sommer = tabelle["datum"].between("2001-07-01", "2001-07-10")
    tabelle.loc[sommer, "tmax"] = 31.0  # 10 heiße Tage am Stück
    tabelle.loc[tabelle["datum"].between("2001-08-01", "2001-08-02"), "tmax"] = 32.0  # zu kurz
    tabelle.loc[tabelle["datum"] == "2001-07-05", "tmin"] = 21.0  # eine Tropennacht
    tabelle.loc[tabelle["datum"].dt.month == 1, ["tmin", "tmax"]] = [-5.0, -1.0]  # Januar
    j = temperaturindizes(tabelle, SCHWELLEN).iloc[0]
    assert j["heisse_tage"] == 12 and j["sommertage"] == 12
    assert (j["hitzewellen"], j["hitzewellentage"], j["laengste_hitzewelle"]) == (1, 10, 10)
    assert j["tropennaechte"] == 1
    assert (j["frosttage"], j["eistage"]) == (31, 31)
    assert j["tagesspanne"] == pytest.approx((tabelle["tmax"] - tabelle["tmin"]).mean())


def test_unvollstaendige_jahre_sind_leer():
    tabelle = jahr_tageswerte(tmax=31.0, tmin=10.0)
    tabelle.loc[tabelle.index[:60], "tmax"] = np.nan  # 60 von 365 Tagen fehlen (> 10 %)
    j = temperaturindizes(tabelle, SCHWELLEN).iloc[0]
    assert np.isnan(j["heisse_tage"]) and np.isnan(j["tagesspanne"])
    assert j["frosttage"] == 0  # Tmin ist vollständig


def test_fuenf_tages_summe():
    tabelle = jahr_tageswerte(niederschlag=0.0)
    tabelle.loc[tabelle.index[10:15], "niederschlag"] = [1, 2, 3, 4, 5]
    tabelle.loc[tabelle.index[20], "niederschlag"] = 12.0
    summen = _summe_mehrtaegig(tabelle, 5)
    assert summen.max() == pytest.approx(15.0)
    assert summen[14] == pytest.approx(15.0)


def test_niederschlagsindizes(monkeypatch):
    monkeypatch.setattr(
        "klima.niederschlag.lade_analyse",
        lambda: {
            "niederschlag": {"niederschlagstag_mm": 1.0, "starkniederschlag_mm": [10.0, 20.0],
                             "perzentil_sehr_nass": 95},
            "vollstaendigkeit": {"mindestanteil_tage": 0.9},
            "anomalien": {"referenzperiode": [2001, 2001], "mindestjahre_referenz": 1},
        },
    )  # fmt: skip
    monkeypatch.setattr("klima.niederschlag.standard_mindestjahre", lambda: 1)
    tabelle = jahr_tageswerte(niederschlag=0.0)
    nass = tabelle.index[100:110]  # 10 nasse Tage am Stück
    tabelle.loc[nass, "niederschlag"] = [2, 2, 2, 2, 2, 2, 2, 2, 15, 25]
    j = niederschlagsindizes(tabelle, referenz=(2001, 2001)).iloc[0]
    assert j["jahressumme"] == pytest.approx(56)
    assert j["niederschlagstage"] == 10
    assert (j["starkniederschlag_10mm"], j["starkniederschlag_20mm"]) == (2, 1)
    assert j["rx1day"] == 25 and j["rx5day"] == pytest.approx(2 + 2 + 2 + 15 + 25)
    assert j["sdii"] == pytest.approx(5.6)
    assert j["cwd"] == 10
    assert j["cdd"] == 365 - 110  # nach dem letzten nassen Tag bis Jahresende
    # 95. Perzentil der nassen Tage liegt zwischen 15 und 25 -> nur 25 mm zählen
    assert j["r95p"] == pytest.approx(25)


def test_dwd_kenntage_gebietsmittel(tmp_path):
    pfad = tmp_path / "regional_averages_txbs_year.txt"
    pfad.write_text(
        "Zeitreihen fuer Gebietsmittel, erstellt am: 20260120\n"
        "Jahr;Jahr;Bayern;Deutschland;\n"
        "1951;year;     3.47;     3.02;\n2025;year;    13.88;    11.06;\n",
        encoding="latin-1",
    )
    werte = dwd.lies_jahresgebietsmittel_kenntage(pfad)
    assert set(werte["kenngroesse"]) == {"heisse_tage"}
    deutschland = werte[werte["gebiet"] == "Deutschland"]
    assert list(deutschland["jahr"]) == [1951, 2025]
    assert deutschland["wert"].iloc[1] == pytest.approx(11.06)


# --- GHCN-Daily ------------------------------------------------------------------------


def test_ghcnd_station(tmp_path):
    pfad = tmp_path / "USW00094728.csv.gz"
    pfad.write_bytes(
        gzip.compress(
            b"USW00094728,20240701,TMAX,317,,,7,\n"
            b"USW00094728,20240701,TMIN,228,,,7,\n"
            b"USW00094728,20240701,PRCP,125,,,7,\n"
            b"USW00094728,20240702,TMAX,999,,X,7,\n"  # Qualitätsprüfung nicht bestanden
            b"USW00094728,20240702,TMIN,200,,,7,\n"
            b"USW00094728,20240702,WSF5,72,,,1,\n"
        )
    )
    werte = ghcnd.lies_station(pfad)
    assert list(werte["datum"].dt.day) == [1, 2]
    assert werte["tmax"].iloc[0] == pytest.approx(31.7)
    assert werte["niederschlag"].iloc[0] == pytest.approx(12.5)
    assert np.isnan(werte["tmax"].iloc[1])  # Q-Flag gesetzt -> verworfen
    assert werte["tmin"].iloc[1] == pytest.approx(20.0)


def test_ghcnd_stationsliste_und_inventar(tmp_path):
    stationen = tmp_path / "ghcnd-stations.txt"

    def zeile(sid, breite, laenge, hoehe, staat, name, gsn, hcn, wmo):
        # Spalten laut NOAA-readme: ID 1-11, LAT 13-20, LON 22-30, ELEV 32-37, STATE 39-40,
        # NAME 42-71, GSN 73-75, HCN/CRN 77-79, WMO-ID 81-85
        return (
            f"{sid:11} {breite:8.4f} {laenge:9.4f} {hoehe:6.1f} {staat:2} {name:30} "
            f"{gsn:3} {hcn:3} {wmo:5}\n"
        )

    stationen.write_text(
        zeile("USW00094728", 40.7789, -73.9692, 39.6, "NY", "NEW YORK CNTRL PK TWR", "", "HCN",
              "72506")
        + zeile("SZ000002220", 47.25, 9.35, 2490.0, "", "SAENTIS", "GSN", "", "06680")
    )  # fmt: skip
    tabelle = ghcnd.lies_stationen(stationen)
    assert list(tabelle["land"]) == ["US", "SZ"]
    assert tabelle["name"].iloc[0] == "NEW YORK CNTRL PK TWR"
    assert tabelle["hoehe"].iloc[1] == pytest.approx(2490.0)

    inventar = tmp_path / "ghcnd-inventory.txt"
    inventar.write_text("USW00094728  40.7789  -73.9692 TMAX 1869 2026\n")
    zeile = ghcnd.lies_inventar(inventar).iloc[0]
    assert (zeile["element"], zeile["von"], zeile["bis"]) == ("TMAX", 1869, 2026)


def test_stationsauswahl():
    datensatz = _datensatz_aus_eintrag(
        "ghcnd_tageswerte",
        {"typ": "stationsauswahl", "url": "https://x.test/by_station/{station}.csv.gz"},
    )
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(404)))
    urls = dateien_ermitteln(client, datensatz, Zeitraum(), ["USW00094728", "SZ000002220"])
    assert urls == [
        "https://x.test/by_station/USW00094728.csv.gz",
        "https://x.test/by_station/SZ000002220.csv.gz",
    ]
    with pytest.raises(ValueError, match="--station"):
        dateien_ermitteln(client, datensatz, Zeitraum(), None)
    with pytest.raises(ValueError, match="Platzhalter"):
        _datensatz_aus_eintrag("x", {"typ": "stationsauswahl", "url": "https://x.test/a.csv"})
