"""Gemeinsames Erscheinungsbild aller Grafiken: Farben, Schrift, deutsches Zahlenformat.

Die kategoriale Palette wurde mit dem Palette-Validator geprüft (Farbsehschwäche,
Helligkeitsband). Gelb und Aqua haben auf hellem Grund weniger als 3:1 Kontrast –
Linien tragen deshalb immer zusätzlich eine direkte Beschriftung bzw. Legende.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.ticker import FuncFormatter

from klima.konfiguration import projektwurzel

# Kategoriale Farben in fester Reihenfolge (nie zyklisch wiederverwenden)
KATEGORIEN = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7"]

# Diagrammfläche und Tinte
FLAECHE = "#fcfcfb"
TINTE = "#0b0b0b"
TINTE_2 = "#52514e"
TINTE_GEDAEMPFT = "#898781"
GITTERLINIE = "#e1e0d9"
GRUNDLINIE = "#c3c2b7"
REFERENZ_FLAECHE = "#f0efec"

# Divergierend: kalt (blau) – neutral (grau) – warm (rot); Mitte = keine Abweichung
DIVERGIEREND = LinearSegmentedColormap.from_list(
    "klima_divergierend",
    [
        "#0d366b",
        "#256abf",
        "#6da7ec",
        "#cde2fb",
        "#f0efec",
        "#f6cfcb",
        "#ee8a83",
        "#e34948",
        "#a32626",
        "#5e1111",
    ],  # fmt: skip
)
# Niederschlag: nass (blau) / trocken (orange)
NASS = "#2a78d6"
TROCKEN = "#eb6834"
NIEDERSCHLAG_DIVERGIEREND = LinearSegmentedColormap.from_list(
    "klima_niederschlag",
    [
        "#7a2e0e",
        "#c4501f",
        "#f0a27f",
        "#f8d9c9",
        "#f0efec",
        "#cde2fb",
        "#6da7ec",
        "#256abf",
        "#0d366b",
    ],
)
FARBSKALEN = {"temperatur": DIVERGIEREND, "niederschlag": NIEDERSCHLAG_DIVERGIEREND}


def robuste_grenze(werte, perzentil: float = 98) -> float:
    """Symmetrische Grenze der Farbskala, unempfindlich gegen einzelne Ausreißer."""
    import numpy as np

    betraege = np.abs(np.asarray(werte, dtype=float))
    return float(np.nanpercentile(betraege, perzentil)) or 1.0


def farben_fuer(namen: list[str], feste: dict[str, str] | None = None) -> dict[str, str]:
    """Ordnet jeder Reihe eine Farbe zu – feste Zuordnung vor Reihenfolge."""
    feste = feste or {}
    freie = iter(f for f in KATEGORIEN if f not in feste.values())
    return {name: feste.get(name) or next(freie) for name in namen}


def zahl(wert: float, nachkommastellen: int | None = None) -> str:
    """Deutsches Zahlenformat mit Dezimalkomma und echtem Minuszeichen."""
    text = f"{wert:g}" if nachkommastellen is None else f"{wert:.{nachkommastellen}f}"
    return text.replace("-", "−").replace(".", ",")


DEUTSCHES_FORMAT = FuncFormatter(lambda x, _: zahl(round(x, 6)))


def anwenden() -> None:
    """Setzt die matplotlib-Grundeinstellungen für alle folgenden Grafiken."""
    mpl.rcParams.update(
        {
            "figure.facecolor": FLAECHE,
            "axes.facecolor": FLAECHE,
            "savefig.facecolor": FLAECHE,
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
            "font.size": 10,
            "text.color": TINTE,
            "axes.labelcolor": TINTE_2,
            "axes.titlesize": 13,
            "axes.titleweight": "bold",
            "axes.titlelocation": "left",
            "axes.edgecolor": GRUNDLINIE,
            "axes.linewidth": 0.8,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "axes.grid.axis": "y",
            "grid.color": GITTERLINIE,
            "grid.linewidth": 0.6,
            "xtick.color": TINTE_GEDAEMPFT,
            "ytick.color": TINTE_GEDAEMPFT,
            "xtick.labelcolor": TINTE_2,
            "ytick.labelcolor": TINTE_2,
            "legend.frameon": False,
            "lines.solid_capstyle": "round",
            "axes.formatter.use_mathtext": False,
            "axes.unicode_minus": True,
        }
    )


def ausgabeverzeichnis(unterordner: str = "") -> Path:
    ordner = projektwurzel() / "ausgabe" / unterordner
    ordner.mkdir(parents=True, exist_ok=True)
    return ordner
