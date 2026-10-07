"""Tests für Anomalien, Jahreswerte, Gitterung, Trends und Grafiken."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from klima.anomalien import anomalien, jahreswerte, klimatologie
from klima.auswertungen import dateiname_sicher
from klima.gitter import flaechenmittel, gitter_mittel, regionalmittel, zellmitte
from klima.trend import gleitendes_mittel, linearer_trend


def monatswerte(stationen: dict[str, float], jahre=range(1951, 1991), anstieg=0.0) -> pd.DataFrame:
    """Künstliche Monatswerte: Grundwert je Station + Jahresgang + linearer Anstieg pro Jahr."""
    zeilen = []
    for stations_id, basis in stationen.items():
        for jahr in jahre:
            for monat in range(1, 13):
                jahresgang = 10 * np.sin((monat - 4) / 12 * 2 * np.pi)
                zeilen.append(
                    (stations_id, jahr, monat, basis + jahresgang + anstieg * (jahr - 1951))
                )
    return pd.DataFrame(zeilen, columns=["stations_id", "jahr", "monat", "tavg"])


# --- Anomalien -------------------------------------------------------------------------


def test_anomalien_entfernen_hoehe_und_jahresgang():
    # Bergstation 8 °C kälter als Talstation – Anomalien müssen trotzdem identisch sein
    werte = monatswerte({"tal": 10.0, "berg": 2.0}, anstieg=0.03)
    ergebnis = anomalien(werte, "tavg", referenz=(1951, 1980), mindestjahre=20)
    tal = ergebnis[ergebnis.stations_id == "tal"].anomalie.to_numpy()
    berg = ergebnis[ergebnis.stations_id == "berg"].anomalie.to_numpy()
    np.testing.assert_allclose(tal, berg)
    # Mittel der Anomalien in der Referenzperiode ist 0
    referenz = ergebnis[ergebnis.jahr <= 1980]
    assert referenz.anomalie.mean() == pytest.approx(0, abs=1e-9)
    # Kein Jahresgang mehr: alle Monate eines Jahres haben dieselbe Anomalie
    assert ergebnis[ergebnis.jahr == 1990].groupby("stations_id").anomalie.std().max() < 1e-9


def test_station_ohne_ausreichende_referenz_wird_verworfen():
    kurz = monatswerte({"kurz": 5.0}, jahre=range(1975, 2000))  # nur 6 Referenzjahre
    lang = monatswerte({"lang": 5.0})
    ergebnis = anomalien(pd.concat([kurz, lang]), "tavg", referenz=(1951, 1980), mindestjahre=20)
    assert set(ergebnis.stations_id) == {"lang"}
    assert len(klimatologie(kurz, "tavg", referenz=(1951, 1980), mindestjahre=20)) == 0


def test_relative_anomalie_fuer_niederschlag():
    werte = pd.DataFrame({"jahr": [1951, 1952, 1953, 1954], "niederschlag": [800, 800, 880, 640]})
    ergebnis = anomalien(
        werte, "niederschlag", gruppe=None, referenz=(1951, 1952), mindestjahre=2, relativ=True
    )
    assert list(ergebnis.anomalie.round(6)) == [0, 0, 10, -20]


def test_jahreswerte_verlangen_vollstaendige_jahre():
    werte = monatswerte({"a": 0.0}, jahre=[2000, 2001])
    werte = werte[~((werte.jahr == 2001) & (werte.monat == 1))]  # Januar 2001 fehlt
    mittel = jahreswerte(werte, "tavg")
    assert list(mittel.jahr) == [2000]
    assert list(jahreswerte(werte, "tavg", mindestmonate=11).jahr) == [2000, 2001]
    summe = jahreswerte(werte.assign(tavg=1.0), "tavg", aggregation="summe")
    assert summe.tavg.iloc[0] == 12


# --- Gitter ----------------------------------------------------------------------------


def test_zellmitte():
    np.testing.assert_allclose(zellmitte([0.1, 4.9, 5.0, -0.1], 5.0, -180.0), [2.5, 2.5, 7.5, -2.5])


def test_dichte_stationen_dominieren_nicht():
    # Drei Stationen in einer Zelle (Anomalie 1), eine Station in einer anderen (Anomalie 0)
    werte = pd.DataFrame(
        {
            "jahr": [2000] * 4,
            "breite": [50.1, 50.2, 50.3, 50.1],
            "laenge": [8.1, 8.2, 8.3, 12.1],
            "anomalie": [1.0, 1.0, 1.0, 0.0],
        }
    )
    gitter = gitter_mittel(werte, groesse=1.0, zeit=("jahr",))
    assert sorted(gitter.stationen) == [1, 3]
    mittel = flaechenmittel(gitter, zeit=("jahr",))
    assert mittel.anomalie.iloc[0] == pytest.approx(0.5)  # nicht 0,75
    assert mittel.zellen.iloc[0] == 2


def test_flaechengewichtung_nach_breite():
    gitter = pd.DataFrame(
        {"jahr": [2000, 2000], "zelle_breite": [0.0, 60.0], "zelle_laenge": [0.0, 0.0],
         "anomalie": [1.0, 0.0]}
    )  # fmt: skip
    mittel = flaechenmittel(gitter, zeit=("jahr",))
    # Gewichte cos(0°) = 1 und cos(60°) = 0,5
    assert mittel.anomalie.iloc[0] == pytest.approx(1 / 1.5)


def test_regionalmittel_mit_stationsliste():
    werte = pd.DataFrame({"stations_id": ["a", "b"], "jahr": [2000, 2000], "anomalie": [2.0, 4.0]})
    stationen = pd.DataFrame(
        {"stations_id": ["a", "b"], "breite": [50.5, 50.5], "laenge": [8.5, 8.6]}
    )
    mittel = regionalmittel(werte, stationen, groesse=1.0, zeit=("jahr",))
    assert mittel.anomalie.iloc[0] == pytest.approx(3.0)


# --- Trend -----------------------------------------------------------------------------


def test_linearer_trend():
    jahre = np.arange(1951, 2021)
    reihe = pd.Series(0.02 * (jahre - 1951) + 1.0, index=jahre)
    trend = linearer_trend(reihe, von=1961)
    assert trend.steigung_pro_dekade == pytest.approx(0.2)
    assert trend.unsicherheit_95 == pytest.approx(0, abs=1e-9)
    assert (trend.von, trend.bis, trend.anzahl) == (1961, 2020, 60)
    assert trend.wert(2000) == pytest.approx(1.98)
    assert trend.text() == "+0,20 ± 0,00 °C/Dekade (1961–2020)"


def test_trend_braucht_drei_werte():
    with pytest.raises(ValueError):
        linearer_trend(pd.Series([1.0, 2.0], index=[2000, 2001]))


def test_gleitendes_mittel_beachtet_luecken():
    reihe = pd.Series([1.0, 2.0, 3.0, 10.0], index=[2000, 2001, 2002, 2010])
    glatt = gleitendes_mittel(reihe, fenster=3, mindestanteil=1.0)
    assert glatt.loc[2001] == pytest.approx(2.0)
    # 2010 hat keine Nachbarn 2009/2011 -> kein Wert, statt 2002 als Nachbarn zu nehmen
    assert np.isnan(glatt.loc[2010])


# --- Grafiken (Rauchtest: werden sie ohne Fehler erzeugt?) ----------------------------


def test_grafiken_werden_gespeichert(tmp_path, monkeypatch):
    monkeypatch.setenv("KLIMA_PROJEKT", str(tmp_path))
    from klima.grafik import interaktiv, statisch

    jahre = np.arange(1900, 2021)
    rng = np.random.default_rng(1)
    reihen = pd.DataFrame(
        {
            "A": 0.01 * (jahre - 1950) + rng.normal(0, 0.3, len(jahre)),
            "B": rng.normal(0, 0.3, len(jahre)),
        },
        index=jahre,
    )
    pfade = statisch.speichern(
        statisch.zeitreihen(
            reihen, "Test", untertitel="Untertitel", referenz=(1951, 1980), quelle="Q"
        ),
        "zeitreihe",
        "test",
    )
    pfade += statisch.speichern(
        statisch.warming_stripes(reihen["A"], "Streifen"), "streifen", "test"
    )
    pfade += statisch.speichern(
        statisch.balken_relativ(reihen["B"] * 10, "Balken"), "balken", "test"
    )
    pfade.append(interaktiv.speichern(interaktiv.zeitreihen(reihen, "Test"), "zeitreihe", "test"))
    for pfad in pfade:
        assert pfad.exists() and pfad.stat().st_size > 1000
    assert pfade[0].parent == tmp_path / "ausgabe" / "test"


def test_dateiname_sicher():
    assert dateiname_sicher("Hohenpeißenberg") == "hohenpeissenberg"
    assert dateiname_sicher("Liebenzell, Bad/ Nagold") == "liebenzell_bad_nagold"
    assert dateiname_sicher("Potsdam (Säkularstation)") == "potsdam_saekularstation"
