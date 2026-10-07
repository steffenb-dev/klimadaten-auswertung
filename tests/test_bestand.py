"""Tests für die Bestandsübersicht der Messstationen."""

from __future__ import annotations

import pandas as pd
from test_aufbereiten import lege_ghcnm_an, projekt  # noqa: F401 (Fixture)

from klima.bestand import _monatliche_zeitraeume, stationsuebersicht, zusammenfassung


def test_monatliche_zeitraeume():
    werte = pd.DataFrame(
        {
            "stations_id": ["a", "a", "a", "b"],
            "jahr": [2000, 2000, 2001, 1990],
            "monat": [1, 3, 2, 6],
            "t": [1.0, 2.0, 3.0, None],
            "n": [None, None, 5.0, 7.0],
        }
    )
    ergebnis = _monatliche_zeitraeume(werte, {"t": "Temperatur", "n": "Niederschlag"})
    a = ergebnis.set_index("stations_id").loc["a"]
    assert (str(a.von), str(a.bis), a.werte) == ("2000-01", "2001-02", 3)
    assert a.vollstaendigkeit == pd.Series([3 / 14 * 100]).astype("float32")[0]
    assert a.messgroessen == "Temperatur, Niederschlag"
    b = ergebnis.set_index("stations_id").loc["b"]
    assert b.messgroessen == "Niederschlag"  # Temperatur nie vorhanden


def test_stationsuebersicht_aus_aufbereiteten_daten(projekt):  # noqa: F811
    lege_ghcnm_an(projekt)
    uebersicht = stationsuebersicht()
    # nur GHCNm QCU ist vorhanden, alle anderen Quellen werden übersprungen
    assert set(uebersicht.quelle) == {"GHCNm QCU"}
    hamburg = uebersicht.set_index("stations_id").loc["GM000010147"]
    assert hamburg["name"] == "HAMBURG_FUHLSBUETTEL"
    assert (str(hamburg.von), str(hamburg.bis)) == ("1950-01", "1990-12")
    assert hamburg.werte == 24
    assert hamburg.aufloesung == "monatlich"

    assert list(stationsuebersicht(laender=["GM"]).stations_id) == ["GM000010147"]
    assert list(stationsuebersicht(name="casey").stations_id) == ["AYM00089606"]
    assert stationsuebersicht(quellen=["dwd_monat"]).empty

    kennzahlen = zusammenfassung(uebersicht).iloc[0]
    assert (kennzahlen.stationen, kennzahlen.laender) == (2, 2)
