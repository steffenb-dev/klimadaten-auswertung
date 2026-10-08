"""Statische Grafiken mit matplotlib (Export als PNG/SVG)."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import TwoSlopeNorm
from matplotlib.figure import Figure
from matplotlib.patches import Patch
from matplotlib.ticker import FuncFormatter

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
    ausdehnung: tuple[float, float, float, float] | None = (5.5, 15.5, 47.0, 55.2),
    quelle: str | None = None,
    groesse: str = "temperatur",
) -> Figure:
    """Karte der Stationen, eingefärbt nach `wert` (divergierend um 0).

    `ausdehnung` (Länge min/max, Breite min/max) – Standard Deutschland; `None` = Weltkarte.

    `groesse` wählt die Farbskala: `temperatur` (blau kalt – rot warm) oder
    `niederschlag` (orange trocken – blau nass). Die Skala endet beim 98. Perzentil;
    extremere Stationen erscheinen in der Randfarbe.
    """
    import cartopy.crs as ccrs
    import cartopy.feature as cfeature

    stil.anwenden()
    welt = ausdehnung is None
    if welt:
        fig, ax = _weltkarte()
    else:
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
        stationen["laenge"], stationen["breite"], c=werte, s=3 if welt else 34,
        cmap=stil.FARBSKALEN[groesse], norm=TwoSlopeNorm(vcenter=0, vmin=-grenze, vmax=grenze),
        edgecolors=stil.FLAECHE if not welt else "none", linewidths=0 if welt else 0.8,
        transform=ccrs.PlateCarree(), zorder=3,
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


def jahresverlauf(
    matrix: pd.DataFrame,
    titel: str,
    hervorheben: list[int],
    einheit: str = "°C",
    y_beschriftung: str = "Tagesmitteltemperatur",
    untertitel: str | None = None,
    referenz: pd.Series | None = None,
    referenz_name: str = "Mittel",
    bezeichnungen: dict[int, str] | None = None,
    quelle: str | None = None,
) -> Figure:
    """Ein Jahr je Linie über Tag 1–365: alle Jahre dünn grau, ausgewählte Jahre farbig.

    `matrix`: Jahre als Zeilen, Tage 1–365 als Spalten (siehe `jahresverlauf.jahresmatrix`).
    `referenz`: optionale Vergleichslinie (Index = Tag 1–365), z. B. Mittel 1951–1980.
    """
    from klima.jahresverlauf import MONATSANFAENGE, MONATSNAMEN

    stil.anwenden()
    bezeichnungen = bezeichnungen or {}
    fig, ax = plt.subplots(figsize=(12, 6.2), layout="constrained")
    tage = matrix.columns.to_numpy()

    uebrige = [j for j in matrix.index if j not in hervorheben]
    for jahr in uebrige:
        ax.plot(tage, matrix.loc[jahr].to_numpy(), color="#9c9a93", lw=0.45, alpha=0.35, zorder=1)
    if uebrige:
        ax.plot([], [], color="#9c9a93", lw=1.2,
                label=f"{min(uebrige)}–{max(uebrige)} ({len(uebrige)} Jahre)")  # fmt: skip
    if referenz is not None:
        ax.plot(referenz.index, referenz.to_numpy(), color=stil.TINTE, lw=1.6, zorder=3,
                label=referenz_name)  # fmt: skip

    farben = stil.farben_fuer([str(j) for j in hervorheben])
    for jahr in hervorheben:
        ax.plot(tage, matrix.loc[jahr].to_numpy(), color=farben[str(jahr)], lw=1.5, zorder=4,
                label=bezeichnungen.get(jahr, str(jahr)))  # fmt: skip

    ax.set_xlim(1, 365)
    ax.set_xticks(MONATSANFAENGE)
    ax.set_xticklabels([])
    ax.set_xticks([a + 14.5 for a in MONATSANFAENGE], MONATSNAMEN, minor=True)
    ax.tick_params(axis="x", which="minor", length=0)
    ax.grid(axis="x", which="major", color=stil.GITTERLINIE, lw=0.6)
    ax.yaxis.set_major_formatter(stil.DEUTSCHES_FORMAT)
    ax.set_ylabel(f"{y_beschriftung} ({einheit})")
    ax.legend(loc="upper left", fontsize=9, ncols=2)
    _titel(ax, titel, untertitel)
    _quelle(fig, quelle)
    return fig


def _weltkarte():
    """Leere Weltkarte (Robinson-Projektion) mit Land, Meer und Küsten."""
    import cartopy.crs as ccrs
    import cartopy.feature as cfeature

    fig = plt.figure(figsize=(11, 6.6), layout="constrained")
    ax = fig.add_subplot(1, 1, 1, projection=ccrs.Robinson())
    ax.set_global()
    ax.add_feature(cfeature.LAND.with_scale("110m"), facecolor="#f6f5f2", edgecolor="none")
    ax.add_feature(cfeature.OCEAN.with_scale("110m"), facecolor="#e9eef3", edgecolor="none")
    ax.add_feature(cfeature.COASTLINE.with_scale("110m"), edgecolor=stil.TINTE_GEDAEMPFT, lw=0.4)
    ax.spines["geo"].set_edgecolor(stil.GRUNDLINIE)
    return fig, ax


def gitterkarte(
    gitter: pd.DataFrame,
    titel: str,
    einheit: str = "°C",
    wert: str = "anomalie",
    zellgroesse: float = 5.0,
    untertitel: str | None = None,
    grenze: float | None = None,
    quelle: str | None = None,
) -> Figure:
    """Weltkarte der Gitterzellen (`zelle_breite`, `zelle_laenge`, `wert`).

    Zellen ohne Daten bleiben frei.
    """
    import cartopy.crs as ccrs

    stil.anwenden()
    breiten = np.arange(-90, 90 + zellgroesse, zellgroesse)
    laengen = np.arange(-180, 180 + zellgroesse, zellgroesse)
    raster = np.full((len(breiten) - 1, len(laengen) - 1), np.nan)
    zeile = ((gitter["zelle_breite"].to_numpy() + 90) // zellgroesse).astype(int)
    spalte = ((gitter["zelle_laenge"].to_numpy() + 180) // zellgroesse).astype(int)
    raster[zeile, spalte] = gitter[wert].to_numpy()

    grenze = grenze or stil.robuste_grenze(gitter[wert])
    fig, ax = _weltkarte()
    flaeche = ax.pcolormesh(
        laengen, breiten, np.ma.masked_invalid(raster), cmap=stil.DIVERGIEREND,
        norm=TwoSlopeNorm(vcenter=0, vmin=-grenze, vmax=grenze), transform=ccrs.PlateCarree(),
        zorder=2,
    )  # fmt: skip
    ax.coastlines(resolution="110m", color=stil.TINTE_GEDAEMPFT, lw=0.4, zorder=3)
    ueberschritten = bool(np.nanmax(np.abs(raster)) > grenze)
    leiste = fig.colorbar(
        flaeche, ax=ax, orientation="horizontal", shrink=0.55, pad=0.03,
        extend="both" if ueberschritten else "neither",
    )  # fmt: skip
    leiste.set_label(einheit, color=stil.TINTE_2)
    leiste.ax.xaxis.set_major_formatter(stil.DEUTSCHES_FORMAT)
    leiste.outline.set_visible(False)
    _titel(ax, titel, untertitel)
    _quelle(fig, quelle)
    return fig


def abdeckung(
    tabelle: pd.DataFrame, titel: str, untertitel: str | None = None, quelle: str | None = None
) -> Figure:
    """Stationsabdeckung je Jahr als zwei übereinanderliegende Diagramme (keine zweite y-Achse):
    oben aktive Stationen, unten Anteil der Erdoberfläche in besetzten Gitterzellen."""
    stil.anwenden()
    fig, (oben, unten) = plt.subplots(2, 1, figsize=(10, 6), sharex=True, layout="constrained")
    for ax, spalte, beschriftung, farbe in (
        (oben, "stationen", "Aktive Stationen", stil.KATEGORIEN[0]),
        (unten, "flaechenanteil", "Erdoberfläche in besetzten Zellen (%)", stil.KATEGORIEN[1]),
    ):
        ax.fill_between(tabelle.index, tabelle[spalte], color=farbe, alpha=0.18, lw=0)
        ax.plot(tabelle.index, tabelle[spalte], color=farbe, lw=1.8)
        ax.set_ylabel(beschriftung)
        ax.set_ylim(bottom=0)
        ax.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:,.0f}".replace(",", ".")))
    oben.margins(x=0.01)
    _titel(oben, titel, untertitel)
    _quelle(fig, quelle)
    return fig


def histogramm(
    werte: pd.Series,
    titel: str,
    einheit: str,
    untertitel: str | None = None,
    quelle: str | None = None,
    klassen: int = 80,
) -> Figure:
    """Verteilung eines Werts (z. B. Trendänderung je Station) mit Markierung von 0 und Median."""
    stil.anwenden()
    werte = werte.dropna()
    grenze = stil.robuste_grenze(werte, 99)
    fig, ax = plt.subplots(figsize=(10, 4.8), layout="constrained")
    ax.hist(werte.clip(-grenze, grenze), bins=klassen, color=stil.KATEGORIEN[0], rwidth=0.85)
    ax.axvline(0, color=stil.GRUNDLINIE, lw=1)
    median = float(werte.median())
    ax.axvline(median, color=stil.TINTE, lw=1.4)
    ax.annotate(
        f"Median {stil.zahl(median, 3)} {einheit}", xy=(median, 1),
        xycoords=("data", "axes fraction"),
        xytext=(6, -12), textcoords="offset points", fontsize=9, color=stil.TINTE,
    )  # fmt: skip
    ax.xaxis.set_major_formatter(stil.DEUTSCHES_FORMAT)
    ax.set_xlabel(einheit)
    ax.set_ylabel("Anzahl Stationen")
    _titel(ax, titel, untertitel)
    _quelle(fig, quelle)
    return fig


def kleine_vielfache(
    felder: dict[str, pd.DataFrame],
    titel: str,
    einheiten: dict[str, str] | None = None,
    untertitel: str | None = None,
    farben: dict[str, str] | None = None,
    glaettung: int | None = 11,
    spalten: int = 3,
    quelle: str | None = None,
) -> Figure:
    """Mehrere kleine Zeitreihen-Diagramme mit eigener y-Achse (eine Größe je Feld).

    `felder`: Feldtitel -> Tabelle (Index = Jahr, Spalten = Reihen). Gleiche Reihen haben
    in allen Feldern dieselbe Farbe; eine gemeinsame Legende steht oben.
    """
    stil.anwenden()
    einheiten = einheiten or {}
    namen = list(dict.fromkeys(n for tabelle in felder.values() for n in tabelle.columns))
    farben = stil.farben_fuer(namen, farben)
    zeilen = int(np.ceil(len(felder) / spalten))
    hoehe = 3.0 * zeilen + 1.4
    fig, achsen = plt.subplots(
        zeilen, spalten, figsize=(4.2 * spalten, hoehe), sharex=True, squeeze=False
    )
    # Feste Kopfzeile (Titel, Untertitel, Legende) und Fußzeile (Quelle) in Zoll
    fig.subplots_adjust(
        left=0.055, right=0.99, top=1 - 1.25 / hoehe, bottom=0.45 / hoehe,
        hspace=0.32, wspace=0.2,
    )  # fmt: skip
    for ax, (feldtitel, tabelle) in zip(achsen.flat, felder.items(), strict=False):
        for name in tabelle.columns:
            reihe = tabelle[name].dropna()
            if reihe.empty:
                continue
            if glaettung:
                ax.plot(reihe.index, reihe.values, color=farben[name], lw=0.7, alpha=0.45)
                glatt = gleitendes_mittel(reihe, glaettung).dropna()
                ax.plot(glatt.index, glatt.values, color=farben[name], lw=1.8)
            else:
                ax.plot(reihe.index, reihe.values, color=farben[name], lw=1.4)
        ax.set_title(feldtitel, fontsize=10.5, pad=4)
        if einheiten.get(feldtitel):
            ax.set_ylabel(einheiten[feldtitel], fontsize=9)
        ax.yaxis.set_major_formatter(stil.DEUTSCHES_FORMAT)
        ax.tick_params(labelsize=8.5)
        ax.margins(x=0.01)
    for ax in list(achsen.flat)[len(felder) :]:
        ax.set_visible(False)
    zoll = 1 / hoehe
    fig.text(0.01, 1 - 0.12 * zoll, titel, ha="left", va="top", fontsize=13, fontweight="bold")
    if untertitel:
        fig.text(0.01, 1 - 0.45 * zoll, untertitel, ha="left", va="top", color=stil.TINTE_2,
                 fontsize=9.5)  # fmt: skip
    griffe = [plt.Line2D([], [], color=farben[n], lw=2) for n in namen]
    fig.legend(griffe, namen, loc="upper left", bbox_to_anchor=(0.005, 1 - 0.7 * zoll),
               ncols=min(len(namen), 3), fontsize=9, frameon=False)  # fmt: skip
    if quelle:
        fig.text(0.01, 0.1 * zoll, quelle, ha="left", va="bottom", color=stil.TINTE_GEDAEMPFT,
                 fontsize=8)  # fmt: skip
    return fig
