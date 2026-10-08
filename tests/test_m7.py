"""Tests für Stundenwerte (MEZ/UTC), Tagesgang, Wärmeinsel, Stadt/Land und Dashboard."""

from __future__ import annotations

import zipfile

import numpy as np
import pandas as pd
import pytest

from klima import stadt_land as sl
from klima import tagesgang as tg
from klima.dashboard import _titel_aus_name, erzeugen
from klima.parser import dwd

PRODUKT = (
    "STATIONS_ID;MESS_DATUM;QN_9;TT_TU;RF_TU;eor\n"
    "       3987;1990010112;    3;   5.0;  80.0;eor\n"
    "       3987;2005010112;    3;   6.0;  70.0;eor\n"
)
METADATEN = (
    "Stations_ID;Von_Datum;Bis_Datum;Stationsname;Parameter;Parameterbeschreibung;Einheit;"
    "Datenquelle (Strukturversion=SV);Zusatz-Info;Besonderheiten;Literaturhinweis;eor;\n"
    "3987;18930101;19911101;Potsdam;TT_TU;Lufttemperatur;°C;Archiv;Stundenwerte in MEZ;;;eor;\n"
    "3987;19920901;20261006;Potsdam;TT_TU;Lufttemperatur;°C;SYNOP;Stundenwerte in UTC;;;eor;\n"
    "Legende: FT  = Folgetag\n"
)


def test_stundenwerte_mez_wird_in_utc_umgerechnet(tmp_path):
    pfad = tmp_path / "stundenwerte_TU_03987_18930101_20251231_hist.zip"
    with zipfile.ZipFile(pfad, "w") as archiv:
        archiv.writestr("produkt_tu_stunde_18930101_20251231_03987.txt", PRODUKT)
        archiv.writestr("Metadaten_Parameter_tu_stunde_03987.txt", METADATEN.encode("latin-1"))
    werte = dwd.lies_stundenwerte_station(pfad)
    # 1990: Angabe in MEZ (12 Uhr) -> 11 Uhr UTC; 2005: bereits UTC
    assert list(werte["zeit_utc"].dt.hour) == [11, 12]
    assert list(werte["temperatur"]) == [5.0, 6.0]


def stunden(station: str, jahre, wert) -> pd.DataFrame:
    zeit = pd.date_range(f"{jahre[0]}-01-01", f"{jahre[-1]}-12-31 23:00", freq="h")
    mez = zeit + pd.Timedelta(hours=1)
    temperatur = wert(mez) if callable(wert) else np.full(len(zeit), float(wert))
    return pd.DataFrame(
        {"stations_id": station, "zeit_utc": zeit, "mez": mez, "jahr": mez.year.astype("int16"),
         "monat": mez.month.astype("int8"), "stunde": mez.hour.astype("int8"),
         "temperatur": temperatur}
    )  # fmt: skip


def test_trend_je_stunde():
    # Nachts (0–5 Uhr) 0,05 °C/Jahr Erwärmung, tagsüber keine
    def wert(mez):
        return np.where(mez.hour < 6, 0.05 * (mez.year - 1951), 0.0)

    daten = stunden("a", range(1951, 1981), wert)
    jahre = tg.jahresmittel_je_stunde(daten, referenz=(1951, 1960), mindestjahre=5)
    trends = tg.trend_je_stunde(jahre, von=1951, bis=1980).set_index("stunde")["trend"]
    assert trends.loc[3] == pytest.approx(0.5, abs=1e-6)  # °C pro Dekade
    assert trends.loc[14] == pytest.approx(0.0, abs=1e-6)


def test_waermeinsel_nur_gemeinsame_stunden():
    stadt = stunden("stadt", [2020], lambda mez: np.where(mez.hour >= 20, 3.0, 1.0))
    land = stunden("land", [2020], 0.0)
    land = land[land["mez"].dt.month != 7]  # Land fehlt im Juli
    ergebnis = tg.waermeinsel(pd.concat([stadt, land]), "stadt", "land")
    sommer = ergebnis[ergebnis["jahreszeit"] == "Sommer"].set_index("stunde")
    assert sommer.loc[21, "differenz"] == pytest.approx(3.0)
    assert sommer.loc[12, "differenz"] == pytest.approx(1.0)
    assert sommer.loc[12, "stunden"] == 30 + 31  # Juni + August
    with pytest.raises(ValueError):
        tg.waermeinsel(stadt, "stadt", "fehlt")


def test_stadt_land_klassifizieren():
    orte = pd.DataFrame(
        {"name": ["Großstadt", "Kleinstadt"], "land": ["X", "X"], "breite": [50.0, 52.0],
         "laenge": [10.0, 10.0], "einwohner": [500_000, 60_000]}
    )  # fmt: skip
    stationen = pd.DataFrame(
        {"stations_id": ["s", "u", "l", "k"],
         # 5 km von der Großstadt, 20 km, 150 km von allem, 15 km von der Kleinstadt
         "breite": [50.045, 50.18, 48.65, 52.135], "laenge": [10.0, 10.0, 10.0, 10.0]}
    )  # fmt: skip
    klassen = sl.klassifizieren(stationen, orte).set_index("stations_id")
    assert list(klassen["lage"]) == ["städtisch", "Übergang", "ländlich", "Übergang"]
    assert klassen.loc["s", "naechste_stadt"] == "Großstadt"
    assert klassen.loc["s", "entfernung_km"] == pytest.approx(5.0, abs=0.1)


def test_dashboard(tmp_path):
    (tmp_path / "deutschland").mkdir()
    (tmp_path / "deutschland" / "warming_stripes.png").write_bytes(b"png")
    (tmp_path / "stationen").mkdir()
    (tmp_path / "stationen" / "03987_potsdam_kenntage.html").write_text("<html>")
    seite = erzeugen(tmp_path).read_text(encoding="utf-8")
    assert "Warming Stripes Deutschland" in seite
    assert 'href="deutschland/warming_stripes.png"' in seite
    assert "03987 Potsdam – Kenntage" in seite
    assert "Global: Stadt minus Land" not in seite  # nicht erzeugte Grafiken fehlen
    assert seite.count("<article") == 2


def test_titel_aus_name():
    assert (
        _titel_aus_name("stationen/usw00094728_ny_city_kenntage")
        == "USW00094728 Ny City – Kenntage"
    )
