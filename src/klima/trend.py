"""Trends und Glättung von Zeitreihen."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats


@dataclass(frozen=True)
class Trend:
    """Linearer Trend einer Jahresreihe."""

    steigung_pro_dekade: float
    unsicherheit_95: float  # halbe Breite des 95-%-Konfidenzintervalls der Steigung
    p_wert: float
    achsenabschnitt: float
    von: int
    bis: int
    anzahl: int

    def wert(self, jahr: float | np.ndarray) -> float | np.ndarray:
        """Wert der Trendgeraden im Jahr `jahr`."""
        return self.achsenabschnitt + self.steigung_pro_dekade / 10 * np.asarray(jahr)

    def text(self, einheit: str = "°C", nachkommastellen: int = 2) -> str:
        """Kurzbeschreibung mit deutschem Zahlenformat, z. B. `+0,25 ± 0,04 °C/Dekade`."""
        f = f"{{:+.{nachkommastellen}f}}"
        steigung = f.format(self.steigung_pro_dekade).replace(".", ",").replace("-", "−")
        unsicherheit = f"{self.unsicherheit_95:.{nachkommastellen}f}".replace(".", ",")
        return f"{steigung} ± {unsicherheit} {einheit}/Dekade ({self.von}–{self.bis})"


def linearer_trend(reihe: pd.Series, von: int | None = None, bis: int | None = None) -> Trend:
    """Kleinste-Quadrate-Gerade durch eine Reihe mit Jahren als Index.

    Hinweis: Das Konfidenzintervall berücksichtigt keine Autokorrelation der Reihe und
    ist daher eher zu schmal.
    """
    reihe = reihe.dropna()
    if von is not None:
        reihe = reihe[reihe.index >= von]
    if bis is not None:
        reihe = reihe[reihe.index <= bis]
    if len(reihe) < 3:
        raise ValueError("Für einen Trend werden mindestens drei Werte benötigt.")
    jahre = reihe.index.to_numpy(dtype=np.float64)
    ergebnis = stats.linregress(jahre, reihe.to_numpy(dtype=np.float64))
    t_wert = stats.t.ppf(0.975, len(reihe) - 2)
    return Trend(
        steigung_pro_dekade=float(ergebnis.slope * 10),
        unsicherheit_95=float(t_wert * ergebnis.stderr * 10),
        p_wert=float(ergebnis.pvalue),
        achsenabschnitt=float(ergebnis.intercept),
        von=int(jahre.min()),
        bis=int(jahre.max()),
        anzahl=len(reihe),
    )


def gleitendes_mittel(reihe: pd.Series, fenster: int = 11, mindestanteil: float = 0.8) -> pd.Series:
    """Zentriertes gleitendes Mittel über `fenster` Jahre (Index = Jahre).

    Fehlende Jahre zählen als Lücke, nicht als Nachbarn; Fenster mit zu wenigen Werten
    bleiben leer.
    """
    reihe = reihe.reindex(range(int(reihe.index.min()), int(reihe.index.max()) + 1))
    return reihe.rolling(
        fenster, center=True, min_periods=max(1, int(np.ceil(fenster * mindestanteil)))
    ).mean()


def steigung_je_gruppe(tabelle: pd.DataFrame, gruppe: str, x: str, y: str) -> pd.Series:
    """Kleinste-Quadrate-Steigung von `y` über `x` je Gruppe, vektorisiert.

    Steigung = Σ(x − x̄)(y − ȳ) / Σ(x − x̄)² – ohne Schleife über Tausende Gruppen.
    Gruppen mit nur einem x-Wert ergeben NaN.
    """
    gruppiert = tabelle.groupby(gruppe, observed=True)
    dx = tabelle[x] - gruppiert[x].transform("mean")
    dy = tabelle[y] - gruppiert[y].transform("mean")
    zaehler = (dx * dy).groupby(tabelle[gruppe], observed=True).sum()
    nenner = (dx * dx).groupby(tabelle[gruppe], observed=True).sum()
    return zaehler / nenner.where(nenner > 0)
