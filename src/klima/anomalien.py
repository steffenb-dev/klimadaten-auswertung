"""Anomalien gegenüber einer Referenzperiode und Jahreswerte.

Anomalien machen Stationen in unterschiedlicher Höhe und Lage vergleichbar: Statt der
absoluten Temperatur wird die Abweichung vom langjährigen Mittel derselben Station
(und desselben Kalendermonats) betrachtet. Für Niederschlag ist die relative Abweichung
in Prozent üblich, da sich die Mengen regional stark unterscheiden.
"""

from __future__ import annotations

import pandas as pd

from klima.konfiguration import lade_analyse


def standard_referenzperiode() -> tuple[int, int]:
    """Referenzperiode aus `konfiguration/analyse.toml` (Standard 1951–1980)."""
    von, bis = lade_analyse()["anomalien"]["referenzperiode"]
    return int(von), int(bis)


def standard_mindestjahre() -> int:
    return int(lade_analyse()["anomalien"]["mindestjahre_referenz"])


def _schluessel(werte: pd.DataFrame, gruppe: str | None) -> list[str]:
    """Gruppierung für die Klimatologie: Gruppe (z. B. Station) und – falls vorhanden – Monat."""
    schluessel = [gruppe] if gruppe else []
    if "monat" in werte:
        schluessel.append("monat")
    return schluessel


def klimatologie(
    werte: pd.DataFrame,
    wert: str,
    gruppe: str | None = "stations_id",
    referenz: tuple[int, int] | None = None,
    mindestjahre: int | None = None,
) -> pd.DataFrame:
    """Mittelwert der Referenzperiode je Gruppe (und Kalendermonat, falls `monat` vorhanden).

    Gruppen mit weniger als `mindestjahre` Werten in der Referenzperiode werden verworfen.
    """
    von, bis = referenz or standard_referenzperiode()
    mindestjahre = standard_mindestjahre() if mindestjahre is None else mindestjahre
    schluessel = _schluessel(werte, gruppe)

    in_referenz = werte[(werte["jahr"] >= von) & (werte["jahr"] <= bis)].dropna(subset=[wert])
    if not schluessel:
        anzahl = len(in_referenz)
        mittel = in_referenz[wert].mean() if anzahl >= mindestjahre else float("nan")
        return pd.DataFrame({"referenzmittel": [mittel], "referenzjahre": [anzahl]})

    statistik = (
        in_referenz.groupby(schluessel, observed=True)[wert]
        .agg(referenzmittel="mean", referenzjahre="count")
        .reset_index()
    )
    return statistik[statistik["referenzjahre"] >= mindestjahre].reset_index(drop=True)


def anomalien(
    werte: pd.DataFrame,
    wert: str,
    gruppe: str | None = "stations_id",
    referenz: tuple[int, int] | None = None,
    mindestjahre: int | None = None,
    relativ: bool = False,
) -> pd.DataFrame:
    """Ergänzt die Spalte `anomalie`: Abweichung vom Mittel der Referenzperiode.

    `relativ=True` liefert die Abweichung in Prozent des Referenzmittels (für Niederschlag).
    Zeilen ohne ausreichende Referenz (siehe `klimatologie`) werden entfernt.
    """
    referenzwerte = klimatologie(werte, wert, gruppe, referenz, mindestjahre)
    schluessel = _schluessel(werte, gruppe)
    if schluessel:
        ergebnis = werte.merge(referenzwerte, on=schluessel, how="inner")
    else:
        ergebnis = werte.assign(**referenzwerte.iloc[0].to_dict())

    if relativ:
        basis = ergebnis["referenzmittel"].where(ergebnis["referenzmittel"] > 0)
        ergebnis["anomalie"] = (ergebnis[wert] / basis - 1) * 100
    else:
        ergebnis["anomalie"] = ergebnis[wert] - ergebnis["referenzmittel"]
    ergebnis = ergebnis.dropna(subset=["anomalie"]).drop(columns=["referenzjahre"])
    sortierung = [s for s in (gruppe, "jahr", "monat") if s and s in ergebnis]
    return ergebnis.sort_values(sortierung, ignore_index=True)


def jahreswerte(
    werte: pd.DataFrame,
    wert: str,
    gruppe: str | None = "stations_id",
    aggregation: str = "mittel",
    mindestmonate: int = 12,
) -> pd.DataFrame:
    """Jahresmittel bzw. Jahressumme aus Monatswerten.

    Jahre mit weniger als `mindestmonate` gültigen Monaten werden verworfen – ein
    fehlender Wintermonat würde das Jahresmittel sonst nach oben verzerren.
    """
    if aggregation not in ("mittel", "summe"):
        raise ValueError("aggregation muss 'mittel' oder 'summe' sein.")
    schluessel = [gruppe, "jahr"] if gruppe else ["jahr"]
    gruppiert = werte.dropna(subset=[wert]).groupby(schluessel, observed=True)[wert]
    ergebnis = gruppiert.agg(["mean" if aggregation == "mittel" else "sum", "count"])
    ergebnis.columns = [wert, "monate"]
    ergebnis = ergebnis[ergebnis["monate"] >= mindestmonate].drop(columns="monate")
    return ergebnis.reset_index()
