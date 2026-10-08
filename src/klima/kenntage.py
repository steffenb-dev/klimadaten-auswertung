"""Klimakenntage und Temperatur-Extremindizes aus Tageswerten (SPEC.md, Abschnitt 3.2).

Je Station und Kalenderjahr:

| Spalte | Definition (Schwellen aus `konfiguration/analyse.toml`) |
|---|---|
| `sommertage` | Tage mit `tmax ≥ 25 °C` |
| `heisse_tage` | Tage mit `tmax ≥ 30 °C` |
| `tropennaechte` | Tage mit `tmin ≥ 20 °C` |
| `frosttage` | Tage mit `tmin < 0 °C` |
| `eistage` | Tage mit `tmax < 0 °C` |
| `hitzewellen` | Anzahl Folgen von mind. 3 aufeinanderfolgenden heißen Tagen |
| `hitzewellentage` | Tage, die zu einer Hitzewelle gehören |
| `laengste_hitzewelle` | Länge der längsten Hitzewelle (Tage) |
| `tmax_mittel`, `tmin_mittel` | Jahresmittel der Tagesmaxima bzw. -minima |
| `tagesspanne` | Jahresmittel von `tmax − tmin` |

Ein Jahr zählt nur, wenn für die jeweilige Größe mindestens 90 % der Tage Werte haben
(`vollstaendigkeit.mindestanteil_tage`). Fehlende Tage werden nicht hochgerechnet; bei
90–100 % Vollständigkeit sind Zählwerte daher leicht unterschätzt.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from klima.konfiguration import lade_analyse

TEMPERATUR_INDIZES = [
    "sommertage", "heisse_tage", "tropennaechte", "frosttage", "eistage",
    "hitzewellen", "hitzewellentage", "laengste_hitzewelle",
    "tmax_mittel", "tmin_mittel", "tagesspanne",
]  # fmt: skip


def schwellen() -> dict:
    konfiguration = lade_analyse()
    return {
        **konfiguration["kenntage"],
        "mindestanteil_tage": float(konfiguration["vollstaendigkeit"]["mindestanteil_tage"]),
    }


def tage_im_jahr(jahre: pd.Series | np.ndarray) -> np.ndarray:
    jahre = np.asarray(jahre, dtype=np.int64)
    schaltjahr = (jahre % 4 == 0) & ((jahre % 100 != 0) | (jahre % 400 == 0))
    return np.where(schaltjahr, 366, 365)


def laeufe(
    tabelle: pd.DataFrame, bedingung: np.ndarray, gruppe: str = "stations_id"
) -> pd.DataFrame:
    """Folgen aufeinanderfolgender Tage, an denen `bedingung` gilt.

    `tabelle` muss nach Gruppe und Datum sortiert sein. Eine Lücke im Datum (fehlender Tag)
    beendet eine Folge. Ergebnis je Folge: Gruppe, `jahr` (des ersten Tags), `laenge`.
    """
    datum = pd.to_datetime(tabelle["datum"]).to_numpy()
    station = tabelle[gruppe].astype(str).to_numpy()
    bedingung = np.asarray(bedingung, dtype=bool)
    fortsetzung = np.zeros(len(tabelle), dtype=bool)
    if len(tabelle) > 1:
        fortsetzung[1:] = (
            bedingung[:-1]
            & (station[1:] == station[:-1])
            & ((datum[1:] - datum[:-1]) == np.timedelta64(1, "D"))
        )
    beginn = bedingung & ~fortsetzung
    folge = np.cumsum(beginn)
    auswahl = bedingung
    ergebnis = pd.DataFrame(
        {
            gruppe: station[auswahl],
            "folge": folge[auswahl],
            "jahr": tabelle["jahr"].to_numpy()[auswahl],
        }
    )
    return (
        ergebnis.groupby("folge")
        .agg(**{gruppe: (gruppe, "first"), "jahr": ("jahr", "first"), "laenge": ("jahr", "size")})
        .reset_index(drop=True)
    )


def _vollstaendig(anzahl: pd.Series, jahre: pd.Series, mindestanteil: float) -> pd.Series:
    return anzahl >= mindestanteil * tage_im_jahr(jahre)


def temperaturindizes(tageswerte: pd.DataFrame, schwellen_: dict | None = None) -> pd.DataFrame:
    """Kenntage je Station und Jahr aus Tageswerten mit `tmax`, `tmin`, `datum`, `jahr`.

    Nicht ausreichend vollständige Werte sind NaN.
    """
    s = schwellen_ or schwellen()
    tageswerte = tageswerte.sort_values(["stations_id", "datum"], ignore_index=True)
    tageswerte["stations_id"] = tageswerte["stations_id"].astype(str)
    tmax, tmin = tageswerte["tmax"], tageswerte["tmin"]
    hilfs = pd.DataFrame(
        {
            "stations_id": tageswerte["stations_id"],
            "jahr": tageswerte["jahr"],
            "tmax_da": tmax.notna(),
            "tmin_da": tmin.notna(),
            "sommertage": tmax >= s["sommertag_tmax"],
            "heisse_tage": tmax >= s["heisser_tag_tmax"],
            "eistage": tmax < s["eistag_tmax"],
            "tropennaechte": tmin >= s["tropennacht_tmin"],
            "frosttage": tmin < s["frosttag_tmin"],
            "tmax_mittel": tmax,
            "tmin_mittel": tmin,
            "tagesspanne": tmax - tmin,
        }
    )
    jahr = hilfs.groupby(["stations_id", "jahr"]).agg(
        tmax_tage=("tmax_da", "sum"),
        tmin_tage=("tmin_da", "sum"),
        sommertage=("sommertage", "sum"),
        heisse_tage=("heisse_tage", "sum"),
        eistage=("eistage", "sum"),
        tropennaechte=("tropennaechte", "sum"),
        frosttage=("frosttage", "sum"),
        tmax_mittel=("tmax_mittel", "mean"),
        tmin_mittel=("tmin_mittel", "mean"),
        tagesspanne=("tagesspanne", "mean"),
    )
    jahr = jahr.reset_index()

    # Hitzewellen: Folgen heißer Tage mit Mindestlänge, dem Jahr ihres ersten Tags zugeordnet
    wellen = laeufe(tageswerte, (tmax >= s["heisser_tag_tmax"]).to_numpy())
    wellen = wellen[wellen["laenge"] >= s["hitzewelle_mindesttage"]]
    je_jahr = wellen.groupby(["stations_id", "jahr"])["laenge"].agg(
        hitzewellen="size", hitzewellentage="sum", laengste_hitzewelle="max"
    )
    jahr = jahr.merge(je_jahr.reset_index(), on=["stations_id", "jahr"], how="left")
    jahr[["hitzewellen", "hitzewellentage", "laengste_hitzewelle"]] = jahr[
        ["hitzewellen", "hitzewellentage", "laengste_hitzewelle"]
    ].fillna(0)

    tmax_ok = _vollstaendig(jahr["tmax_tage"], jahr["jahr"], s["mindestanteil_tage"])
    tmin_ok = _vollstaendig(jahr["tmin_tage"], jahr["jahr"], s["mindestanteil_tage"])
    for spalte in ("sommertage", "heisse_tage", "eistage", "tmax_mittel", "hitzewellen",
                   "hitzewellentage", "laengste_hitzewelle"):  # fmt: skip
        jahr[spalte] = jahr[spalte].where(tmax_ok)
    for spalte in ("tropennaechte", "frosttage", "tmin_mittel"):
        jahr[spalte] = jahr[spalte].where(tmin_ok)
    jahr["tagesspanne"] = jahr["tagesspanne"].where(tmax_ok & tmin_ok)
    return jahr[["stations_id", "jahr", *TEMPERATUR_INDIZES]]
