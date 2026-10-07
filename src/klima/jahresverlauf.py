"""Tägliches Gebietsmittel und Jahresverlauf (Tag 1–365) für Deutschland.

Schaltjahre: Es wird ein 365-Tage-Kalender verwendet (CF-Konvention `noleap`/`365_day`):
Jeder Kalendertag hat in jedem Jahr dieselbe Position (1. März = Tag 60). Der 29. Februar
erhält keinen eigenen Tag. Für seine Anomalie dient – wie bei den täglichen Klimanormalwerten
der NOAA – der Mittelwert der Referenz vom 28. Februar und 1. März. In Darstellungen über
Tag 1–365 entfällt er; in Monats- und Jahresmitteln ist er enthalten.

Verfahren für das tägliche Gebietsmittel:
1. Referenzmittel je Station und Kalendertag (Referenzperiode, Standard 1951–1980), über
   31 Tage zirkulär geglättet – 30 Einzelwerte je Kalendertag streuen sonst zu stark.
2. Tägliche Anomalie je Station = Tageswert − Referenzmittel des Kalendertags.
3. Gitterung (1°) und Flächengewichtung der Anomalien je Tag.
4. Absolute Temperatur = Referenzmittel für Deutschland (ebenfalls gegittert) + Anomalie.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from klima import einlesen
from klima.anomalien import standard_mindestjahre, standard_referenzperiode
from klima.deutschland import standard_zellgroesse
from klima.gitter import regionalmittel

TAGE = 365
SCHALTTAG = 0  # Kennung für den 29. Februar
# Erster Tag jedes Monats im 365-Tage-Kalender (für Achsenbeschriftungen)
MONATSANFAENGE = [1, 32, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335]
MONATSNAMEN = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]


def tag_im_jahr(datum: pd.Series) -> np.ndarray:
    """Tag 1–365 im 365-Tage-Kalender; der 29. Februar erhält `SCHALTTAG` (0)."""
    datum = pd.to_datetime(datum)
    tag = datum.dt.dayofyear.to_numpy().astype(np.int16)
    schaltjahr = datum.dt.is_leap_year.to_numpy()
    nach_februar = datum.dt.month.to_numpy() > 2
    tag = tag - (schaltjahr & nach_februar)
    tag[(datum.dt.month.to_numpy() == 2) & (datum.dt.day.to_numpy() == 29)] = SCHALTTAG
    return tag


def _zirkulaer_glaetten(matrix: np.ndarray, fenster: int, mindestanteil: float) -> np.ndarray:
    """Gleitendes Mittel je Zeile über den Jahreskreis (31.12. ist Nachbar des 1.1.)."""
    halb = fenster // 2
    erweitert = np.concatenate([matrix[:, -halb:], matrix, matrix[:, :halb]], axis=1)
    gueltig = np.isfinite(erweitert)
    summe = np.cumsum(np.where(gueltig, erweitert, 0.0), axis=1)
    anzahl = np.cumsum(gueltig, axis=1)
    summe = np.concatenate([np.zeros((len(matrix), 1)), summe], axis=1)
    anzahl = np.concatenate([np.zeros((len(matrix), 1)), anzahl], axis=1)
    fenster_summe = summe[:, fenster:] - summe[:, :-fenster]
    fenster_anzahl = anzahl[:, fenster:] - anzahl[:, :-fenster]
    with np.errstate(invalid="ignore", divide="ignore"):
        mittel = fenster_summe / fenster_anzahl
    mittel[fenster_anzahl < mindestanteil * fenster] = np.nan
    return mittel


def tagesklimatologie(
    werte: pd.DataFrame,
    wert: str,
    referenz: tuple[int, int],
    mindestjahre: int,
    glaettung: int = 31,
) -> tuple[pd.Index, np.ndarray]:
    """Geglättetes Referenzmittel je Station (Zeilen) und Kalendertag 1–365 (Spalten).

    Ein Kalendertag braucht mindestens `mindestjahre` Werte in der Referenzperiode.
    """
    in_ref = werte[(werte["jahr"] >= referenz[0]) & (werte["jahr"] <= referenz[1])]
    in_ref = in_ref[in_ref["tag"] != SCHALTTAG].dropna(subset=[wert])
    statistik = in_ref.groupby(["stations_id", "tag"], observed=True)[wert].agg(["mean", "count"])
    statistik = statistik[statistik["count"] >= mindestjahre]["mean"].unstack("tag")
    statistik = statistik.reindex(columns=range(1, TAGE + 1))
    geglaettet = _zirkulaer_glaetten(statistik.to_numpy(dtype=np.float64), glaettung, 0.8)
    return statistik.index.astype(str), geglaettet


def deutschland_tagesmittel(
    wert: str = "tmittel",
    referenz: tuple[int, int] | None = None,
    groesse: float | None = None,
    mindestjahre: int | None = None,
) -> pd.DataFrame:
    """Tägliches Gebietsmittel für Deutschland aus den DWD-Stationen.

    Ergebnis je Datum: `jahr`, `tag` (1–365, 0 = 29.02.), `anomalie`, `referenz`
    (Referenzmittel des Kalendertags), `wert` (absolut = referenz + anomalie), `zellen`
    (Anzahl besetzter 1°-Gitterzellen – Maß für die Abdeckung).
    """
    referenz = referenz or standard_referenzperiode()
    groesse = groesse or standard_zellgroesse()
    mindestjahre = standard_mindestjahre() if mindestjahre is None else mindestjahre

    werte = einlesen.dwd_tageswerte(spalten=["stations_id", "datum", "jahr", wert])
    werte = werte.dropna(subset=[wert])
    werte["stations_id"] = werte["stations_id"].astype(str)
    werte["tag"] = tag_im_jahr(werte["datum"])

    stationen_ref, klima = tagesklimatologie(werte, wert, referenz, mindestjahre)
    # Referenz für den 29.02.: Mittel aus 28.02. (Tag 59) und 01.03. (Tag 60)
    klima_mit_schalttag = np.concatenate([(klima[:, 58:59] + klima[:, 59:60]) / 2, klima], axis=1)

    # Anomalien per Index-Zugriff statt Join (schnell bei ~20 Mio. Zeilen)
    zeile = pd.Index(stationen_ref).get_indexer(werte["stations_id"])
    hat_referenz = zeile >= 0
    werte = werte[hat_referenz]
    werte["anomalie"] = (
        werte[wert].to_numpy() - klima_mit_schalttag[zeile[hat_referenz], werte["tag"].to_numpy()]
    )
    werte = werte.dropna(subset=["anomalie"])

    stationen = einlesen.dwd_stationen("tag")
    taeglich = regionalmittel(werte, stationen, groesse=groesse, zeit=("datum",))

    # Referenzmittel Deutschland je Kalendertag, ebenfalls gegittert und flächengewichtet
    klima_lang = pd.DataFrame(klima, index=stationen_ref, columns=range(1, TAGE + 1))
    klima_lang = klima_lang.rename_axis("stations_id").reset_index()
    klima_lang = klima_lang.melt("stations_id", var_name="tag", value_name="klima").dropna()
    klima_de = regionalmittel(
        klima_lang, stationen, wert="klima", groesse=groesse, zeit=("tag",)
    ).set_index("tag")["klima"]
    klima_de.loc[SCHALTTAG] = (klima_de.loc[59] + klima_de.loc[60]) / 2

    taeglich["datum"] = pd.to_datetime(taeglich["datum"])
    taeglich["jahr"] = taeglich["datum"].dt.year.astype("int16")
    taeglich["tag"] = tag_im_jahr(taeglich["datum"])
    taeglich["referenz"] = taeglich["tag"].map(klima_de).astype("float64")
    taeglich[wert] = taeglich["referenz"] + taeglich["anomalie"]
    return taeglich[["datum", "jahr", "tag", wert, "anomalie", "referenz", "zellen"]]


def jahresmatrix(tagesmittel: pd.DataFrame, wert: str = "tmittel") -> pd.DataFrame:
    """Jahre als Zeilen, Tage 1–365 als Spalten (29. Februar entfällt)."""
    ohne_schalttag = tagesmittel[tagesmittel["tag"] != SCHALTTAG]
    return ohne_schalttag.pivot(index="jahr", columns="tag", values=wert).reindex(
        columns=range(1, TAGE + 1)
    )


def vollstaendige_jahre(
    tagesmittel: pd.DataFrame, mindestzellen: int, mindestanteil_tage: float = 1.0
) -> list[int]:
    """Jahre, in denen (fast) jeder Tag mindestens `mindestzellen` besetzte Zellen hat."""
    gueltige_tage = (
        tagesmittel[tagesmittel["zellen"] >= mindestzellen].groupby("jahr")["datum"].count()
    )
    return [
        int(jahr)
        for jahr, anzahl in gueltige_tage.items()
        if anzahl
        >= mindestanteil_tage * (366 if pd.Timestamp(int(jahr), 1, 1).is_leap_year else 365)
    ]


def monatsvergleich_mit_dwd(tagesmittel: pd.DataFrame, wert: str = "tmittel") -> pd.DataFrame:
    """Validierung: Monatsmittel aus dem eigenen Tagesmittel vs. offizielles DWD-Gebietsmittel."""
    eigen = (
        tagesmittel.assign(monat=tagesmittel["datum"].dt.month)
        .groupby(["jahr", "monat"])
        .agg(eigen=(wert, "mean"), tage=(wert, "count"))
        .reset_index()
    )
    offiziell = einlesen.dwd_gebietsmittel("temperatur", gebiete=["Deutschland"])
    vergleich = eigen.merge(
        offiziell.rename(columns={"temperatur": "dwd"})[["jahr", "monat", "dwd"]],
        on=["jahr", "monat"],
    )
    vergleich["differenz"] = vergleich["eigen"] - vergleich["dwd"]
    return vergleich
