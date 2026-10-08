"""Niederschlagsindizes aus Tageswerten (SPEC.md, Abschnitt 3.3; angelehnt an ETCCDI).

Je Station und Kalenderjahr:

| Spalte | Definition (Schwellen aus `konfiguration/analyse.toml`) |
|---|---|
| `jahressumme` | Summe des Niederschlags (mm) |
| `niederschlagstage` | Tage mit `≥ 1 mm` |
| `starkniederschlag_10mm`, `starkniederschlag_20mm` | Tage mit `≥ 10 mm` bzw. `≥ 20 mm` |
| `rx1day` | größte Tagessumme (mm) |
| `rx5day` | größte Summe über 5 aufeinanderfolgende Tage (mm) |
| `sdii` | mittlere Intensität an Niederschlagstagen (mm/Tag) |
| `cdd` | längste Trockenperiode: aufeinanderfolgende Tage `< 1 mm` |
| `cwd` | längste Nassperiode: aufeinanderfolgende Tage `≥ 1 mm` |
| `r95p` | Summe an sehr nassen Tagen (> 95. Perzentil der Niederschlagstage der Referenzperiode) |
| `r95p_anteil` | `r95p` in % der Jahressumme |

Ein Jahr zählt nur bei mindestens 90 % Tagen mit Werten. Trocken- und Nassperioden werden
innerhalb eines Kalenderjahres gezählt; ein fehlender Tag beendet die Periode.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from klima.anomalien import standard_mindestjahre, standard_referenzperiode
from klima.kenntage import _vollstaendig, laeufe
from klima.konfiguration import lade_analyse

NIEDERSCHLAG_INDIZES = [
    "jahressumme", "niederschlagstage", "starkniederschlag_10mm", "starkniederschlag_20mm",
    "rx1day", "rx5day", "sdii", "cdd", "cwd", "r95p", "r95p_anteil",
]  # fmt: skip


def _summe_mehrtaegig(tageswerte: pd.DataFrame, tage: int) -> np.ndarray:
    """Summe über die letzten `tage` Kalendertage je Station (fehlende Tage zählen als 0)."""
    station = tageswerte["stations_id"].astype("category").cat.codes.to_numpy().astype(np.int64)
    tag = (pd.to_datetime(tageswerte["datum"]) - pd.Timestamp("1700-01-01")).dt.days.to_numpy()
    schluessel = station * 1_000_000 + tag
    kumuliert = np.concatenate([[0.0], np.cumsum(tageswerte["niederschlag"].fillna(0).to_numpy())])
    beginn = np.searchsorted(schluessel, schluessel - (tage - 1), side="left")
    return kumuliert[np.arange(1, len(schluessel) + 1)] - kumuliert[beginn]


def perzentil_sehr_nass(
    tageswerte: pd.DataFrame,
    referenz: tuple[int, int] | None = None,
    perzentil: float | None = None,
    mindestjahre: int | None = None,
) -> pd.Series:
    """95. Perzentil (Standard) der Niederschlagstage je Station in der Referenzperiode."""
    referenz = referenz or standard_referenzperiode()
    konfiguration = lade_analyse()["niederschlag"]
    perzentil = perzentil or float(konfiguration["perzentil_sehr_nass"])
    mindestjahre = standard_mindestjahre() if mindestjahre is None else mindestjahre
    schwelle_nass = float(konfiguration["niederschlagstag_mm"])

    in_ref = tageswerte[(tageswerte["jahr"] >= referenz[0]) & (tageswerte["jahr"] <= referenz[1])]
    jahre = (
        in_ref.dropna(subset=["niederschlag"])
        .groupby("stations_id", observed=True)["jahr"]
        .nunique()
    )
    nass = in_ref[in_ref["niederschlag"] >= schwelle_nass]
    werte = nass.groupby("stations_id", observed=True)["niederschlag"].quantile(perzentil / 100)
    werte.index = werte.index.astype(str)
    jahre.index = jahre.index.astype(str)
    return werte[jahre.reindex(werte.index).fillna(0) >= mindestjahre]


def niederschlagsindizes(
    tageswerte: pd.DataFrame,
    referenz: tuple[int, int] | None = None,
    mindestanteil_tage: float | None = None,
) -> pd.DataFrame:
    """Niederschlagsindizes je Station und Jahr.

    Erwartet Tageswerte mit den Spalten `stations_id`, `datum`, `jahr`, `niederschlag`.
    """
    konfiguration = lade_analyse()
    nass_mm = float(konfiguration["niederschlag"]["niederschlagstag_mm"])
    stark_10, stark_20 = (float(x) for x in konfiguration["niederschlag"]["starkniederschlag_mm"])
    mindestanteil = mindestanteil_tage or float(
        konfiguration["vollstaendigkeit"]["mindestanteil_tage"]
    )

    tageswerte = tageswerte.sort_values(["stations_id", "datum"], ignore_index=True)
    tageswerte["stations_id"] = tageswerte["stations_id"].astype(str)
    rr = tageswerte["niederschlag"]
    p95 = perzentil_sehr_nass(tageswerte, referenz)
    schwelle_95 = tageswerte["stations_id"].map(p95)
    sehr_nass = rr > schwelle_95

    hilfs = pd.DataFrame(
        {
            "stations_id": tageswerte["stations_id"],
            "jahr": tageswerte["jahr"],
            "da": rr.notna(),
            "rr": rr,
            "nass": rr >= nass_mm,
            "stark_10": rr >= stark_10,
            "stark_20": rr >= stark_20,
            "rr_nass": rr.where(rr >= nass_mm),
            "rx5": _summe_mehrtaegig(tageswerte, 5),
            "r95": rr.where(sehr_nass, 0.0).where(schwelle_95.notna()),
        }
    )
    jahr = hilfs.groupby(["stations_id", "jahr"]).agg(
        tage=("da", "sum"),
        jahressumme=("rr", "sum"),
        niederschlagstage=("nass", "sum"),
        starkniederschlag_10mm=("stark_10", "sum"),
        starkniederschlag_20mm=("stark_20", "sum"),
        rx1day=("rr", "max"),
        rx5day=("rx5", "max"),
        sdii=("rr_nass", "mean"),
        r95p=("r95", "sum"),
    )
    jahr = jahr.reset_index()
    jahr["r95p"] = jahr["r95p"].where(jahr["stations_id"].isin(p95.index))
    jahr["r95p_anteil"] = jahr["r95p"] / jahr["jahressumme"].where(jahr["jahressumme"] > 0) * 100

    for name, bedingung in (
        ("cdd", (rr < nass_mm).to_numpy()),
        ("cwd", (rr >= nass_mm).to_numpy()),
    ):
        perioden = laeufe(tageswerte, bedingung)
        laengste = perioden.groupby(["stations_id", "jahr"])["laenge"].max().rename(name)
        jahr = jahr.merge(laengste.reset_index(), on=["stations_id", "jahr"], how="left")
        jahr[name] = jahr[name].fillna(0)

    ok = _vollstaendig(jahr["tage"], jahr["jahr"], mindestanteil)
    for spalte in NIEDERSCHLAG_INDIZES:
        jahr[spalte] = jahr[spalte].where(ok)
    return jahr[["stations_id", "jahr", *NIEDERSCHLAG_INDIZES]]
