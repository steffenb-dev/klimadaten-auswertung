"""Statische Grafiken mit matplotlib (Export als PNG/SVG)."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import TwoSlopeNorm
from matplotlib.figure import Figure
from matplotlib.patches import Patch

from klima.grafik import stil
from klima.trend import gleitendes_mittel


def _titel(ax, titel: str, untertitel: str | None) -> None:
    ax.set_title(titel, pad=24 if untertitel else 10)
    if untertitel:
        ax.text(0, 1.02, untertitel, transform=ax.transAxes, color=stil.TINTE_2, fontsize=9.5)


def _quelle(fig: Figure, quelle: str | None) -> None:
    """Quellenangabe unten links; `supxlabel` sorgt dafür, dass das Layout Platz reserviert."""
    if quelle:
        fig.supxlabel(quelle, x=0.01, ha="left", color=stil.TINTE_GEDAEMPFT, fontsize=8)


def zeitreihen(
    reihen: pd.DataFrame,
    titel: str,
    einheit: str = "°C",
    untertitel: str | None = None,
    glaettung: int | None = 11,
    referenz: tuple[int, int] | None = None,
    farben: dict[str, str] | None = None,
    quelle: str | None = None,
) -> Figure:
    """Jahresreihen (Spalten) als Linien: dünn die Jahreswerte, kräftig das gleitende Mittel.

    Jede Reihe wird am rechten Ende direkt beschriftet; die Referenzperiode ist hinterlegt.
    """
    stil.anwenden()
    farben = stil.farben_fuer(list(reihen.columns), farben)
    fig, ax = plt.subplots(figsize=(10, 5.2), layout="constrained")

    if referenz:
        ax.axvspan(referenz[0], referenz[1], color=stil.REFERENZ_FLAECHE, zorder=0, lw=0)
        ax.text(
            (referenz[0] + referenz[1]) / 2, 1.0, f"Referenz {referenz[0]}–{referenz[1]}",
            transform=ax.get_xaxis_transform(), ha="center", va="top",
            color=stil.TINTE_GEDAEMPFT, fontsize=8.5,
        )  # fmt: skip
    ax.axhline(0, color=stil.GRUNDLINIE, lw=0.8, zorder=1)

    enden = []
    for name in reihen.columns:
        reihe = reihen[name].dropna()
        farbe = farben[name]
        if glaettung:
            ax.plot(reihe.index, reihe.values, color=farbe, lw=0.8, alpha=0.45, zorder=2)
            glatt = gleitendes_mittel(reihe, glaettung).dropna()
            ax.plot(glatt.index, glatt.values, color=farbe, lw=2, label=name, zorder=3)
            enden.append((name, glatt.index[-1], glatt.iloc[-1]))
        else:
            ax.plot(reihe.index, reihe.values, color=farbe, lw=1.6, label=name, zorder=3)
            enden.append((name, reihe.index[-1], reihe.iloc[-1]))

    # Direkte Beschriftung, bei Überlappung vertikal auseinanderziehen
    if len(enden) <= 4:
        y_spanne = np.subtract(*ax.get_ylim()[::-1])
        abstand = 0.045 * y_spanne
        positionen: list[float] = []
        for name, x, y in sorted(enden, key=lambda e: e[2]):
            y_text = max(y, positionen[-1] + abstand) if positionen else y
            positionen.append(y_text)
            ax.annotate(
                name.split(" (")[0], xy=(x, y), xytext=(8, (y_text - y) / y_spanne * 260),
                textcoords="offset points", va="center", fontsize=8.5, color=stil.TINTE_2,
                annotation_clip=False,
            )  # fmt: skip

    ax.yaxis.set_major_formatter(stil.DEUTSCHES_FORMAT)
    ax.set_ylabel(f"Abweichung ({einheit})")
    ax.margins(x=0.01)
    ax.legend(loc="upper left", fontsize=8.5)
    _titel(ax, titel, untertitel)
    _quelle(fig, quelle)
    return fig


def warming_stripes(
    reihe: pd.Series,
    titel: str | None = None,
    grenze: float | None = None,
    quelle: str | None = None,
) -> Figure:
    """„Warming Stripes“: ein Farbstreifen je Jahr, blau = kälter, rot = wärmer als die Referenz.

    `grenze` legt die Farbskala symmetrisch fest (Standard: größte Abweichung, mind. 0,5).
    """
    stil.anwenden()
    reihe = reihe.dropna()
    jahre = np.arange(int(reihe.index.min()), int(reihe.index.max()) + 1)
    werte = reihe.reindex(jahre)
    grenze = grenze or max(0.5, float(np.nanmax(np.abs(werte))))
    norm = TwoSlopeNorm(vcenter=0, vmin=-grenze, vmax=grenze)

    fig, ax = plt.subplots(figsize=(10, 2.8), layout="constrained")
    farben = [stil.DIVERGIEREND(norm(w)) if np.isfinite(w) else stil.FLAECHE for w in werte]
    ax.bar(jahre, 1, width=1.0, color=farben, linewidth=0)
    ax.set_xlim(jahre[0] - 0.5, jahre[-1] + 0.5)
    ax.set_ylim(0, 1)
    ax.axis("off")
    for x, ha in ((jahre[0] - 0.5, "left"), (jahre[-1] + 0.5, "right")):
        ax.text(x, -0.06, str(int(x + (0.5 if ha == "left" else -0.5))), ha=ha, va="top",
                fontsize=9, color=stil.TINTE_2, transform=ax.get_xaxis_transform())  # fmt: skip
    if titel:
        ax.set_title(titel, loc="left")
    _quelle(fig, quelle)
    return fig


def balken_relativ(
    reihe: pd.Series,
    titel: str,
    untertitel: str | None = None,
    einheit: str = "%",
    glaettung: int | None = 11,
    quelle: str | None = None,
) -> Figure:
    """Relative Abweichungen als Balken (nass blau, trocken orange) plus gleitendes Mittel."""
    stil.anwenden()
    reihe = reihe.dropna()
    fig, ax = plt.subplots(figsize=(10, 4.8), layout="constrained")
    farben = np.where(reihe.values >= 0, stil.NASS, stil.TROCKEN)
    ax.bar(reihe.index, reihe.values, width=0.75, color=farben, linewidth=0, zorder=2)
    ax.axhline(0, color=stil.GRUNDLINIE, lw=0.8, zorder=1)
    if glaettung:
        glatt = gleitendes_mittel(reihe, glaettung).dropna()
        ax.plot(glatt.index, glatt.values, color=stil.TINTE, lw=1.8, zorder=3,
                label=f"{glaettung}-jähriges Mittel")  # fmt: skip
    handles, _ = ax.get_legend_handles_labels()
    handles += [
        Patch(color=stil.NASS, label="nasser als Referenz"),
        Patch(color=stil.TROCKEN, label="trockener als Referenz"),
    ]
    ax.legend(handles=handles, loc="upper left", fontsize=8.5, ncols=3)
    ax.yaxis.set_major_formatter(stil.DEUTSCHES_FORMAT)
    ax.set_ylabel(f"Abweichung ({einheit})")
    ax.margins(x=0.01)
    _titel(ax, titel, untertitel)
    _quelle(fig, quelle)
    return fig


def stationskarte(
    stationen: pd.DataFrame,
    wert: str,
    titel: str,
    einheit: str,
    untertitel: str | None = None,
    ausdehnung: tuple[float, float, float, float] = (5.5, 15.5, 47.0, 55.2),
    quelle: str | None = None,
    groesse: str = "temperatur",
) -> Figure:
    """Karte der Stationen, eingefärbt nach `wert` (divergierend um 0).

    `groesse` wählt die Farbskala: `temperatur` (blau kalt – rot warm) oder
    `niederschlag` (orange trocken – blau nass). Die Skala endet beim 98. Perzentil;
    extremere Stationen erscheinen in der Randfarbe.
    """
    import cartopy.crs as ccrs
    import cartopy.feature as cfeature

    stil.anwenden()
    projektion = ccrs.LambertConformal(central_longitude=10.5, central_latitude=51)
    fig = plt.figure(figsize=(7.2, 8.4), layout="constrained")
    ax = fig.add_subplot(1, 1, 1, projection=projektion)
    ax.set_extent(ausdehnung, crs=ccrs.PlateCarree())
    ax.add_feature(cfeature.LAND.with_scale("10m"), facecolor="#f6f5f2", edgecolor="none")
    ax.add_feature(cfeature.OCEAN.with_scale("10m"), facecolor="#e9eef3", edgecolor="none")
    ax.add_feature(cfeature.BORDERS.with_scale("10m"), edgecolor=stil.TINTE_GEDAEMPFT, lw=0.7)
    ax.add_feature(cfeature.COASTLINE.with_scale("10m"), edgecolor=stil.TINTE_GEDAEMPFT, lw=0.5)

    werte = stationen[wert].to_numpy()
    grenze = stil.robuste_grenze(werte)
    punkte = ax.scatter(
        stationen["laenge"], stationen["breite"], c=werte, s=34,
        cmap=stil.FARBSKALEN[groesse], norm=TwoSlopeNorm(vcenter=0, vmin=-grenze, vmax=grenze),
        edgecolors=stil.FLAECHE, linewidths=0.8, transform=ccrs.PlateCarree(), zorder=3,
    )  # fmt: skip
    ueberschritten = bool(np.nanmax(np.abs(werte)) > grenze)
    leiste = fig.colorbar(
        punkte, ax=ax, orientation="horizontal", shrink=0.7, pad=0.02,
        extend="both" if ueberschritten else "neither",
    )  # fmt: skip
    leiste.set_label(einheit, color=stil.TINTE_2)
    leiste.ax.xaxis.set_major_formatter(stil.DEUTSCHES_FORMAT)
    leiste.outline.set_visible(False)
    _titel(ax, titel, untertitel)
    _quelle(fig, quelle)
    return fig


def speichern(
    fig: Figure, name: str, unterordner: str = "", formate: tuple[str, ...] = ("png", "svg")
) -> list[Path]:
    """Speichert die Grafik nach `ausgabe/<unterordner>/<name>.<format>` und schließt sie."""
    ordner = stil.ausgabeverzeichnis(unterordner)
    pfade = []
    for endung in formate:
        pfad = ordner / f"{name}.{endung}"
        fig.savefig(pfad, dpi=160 if endung == "png" else None)
        pfade.append(pfad)
    plt.close(fig)
    return pfade
