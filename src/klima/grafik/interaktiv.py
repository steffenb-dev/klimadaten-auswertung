"""Interaktive Grafiken mit plotly (Export als eigenständige HTML-Datei).

Interaktiv dort, wo Zoomen, Hovern und Ein-/Ausblenden Mehrwert bringen: Zeitreihen
mit mehreren Quellen und Stationskarten.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from matplotlib.colors import to_hex

from klima.grafik import stil
from klima.trend import gleitendes_mittel


def _plotly_skala(groesse: str = "temperatur", stufen: int = 11) -> list[list]:
    skala = stil.FARBSKALEN[groesse]
    return [[i / (stufen - 1), to_hex(skala(i / (stufen - 1)))] for i in range(stufen)]


def _grundlayout(fig: go.Figure, titel: str, untertitel: str | None) -> go.Figure:
    text = f"<b>{titel}</b>" + (
        f"<br><span style='font-size:13px;color:{stil.TINTE_2}'>{untertitel}</span>"
        if untertitel
        else ""
    )
    fig.update_layout(
        title={"text": text, "x": 0.01, "xanchor": "left"},
        template="simple_white",
        paper_bgcolor=stil.FLAECHE,
        plot_bgcolor=stil.FLAECHE,
        font={"family": "system-ui, -apple-system, Segoe UI, sans-serif", "color": stil.TINTE},
        separators=",.",  # Dezimalkomma, Punkt als Tausendertrennzeichen
        margin={"l": 60, "r": 30, "t": 90, "b": 50},
        hoverlabel={"bgcolor": "white"},
    )
    return fig


def zeitreihen(
    reihen: pd.DataFrame,
    titel: str,
    einheit: str = "°C",
    untertitel: str | None = None,
    glaettung: int | None = 11,
    referenz: tuple[int, int] | None = None,
    farben: dict[str, str] | None = None,
) -> go.Figure:
    """Jahresreihen mit gemeinsamer Hover-Anzeige je Jahr; Reihen per Legende ein-/ausblendbar."""
    farben = stil.farben_fuer(list(reihen.columns), farben)
    fig = go.Figure()
    for name in reihen.columns:
        reihe = reihen[name].dropna()
        gruppe = name
        fig.add_trace(
            go.Scatter(
                x=reihe.index, y=reihe.values, name=name, legendgroup=gruppe,
                mode="lines", line={"color": farben[name], "width": 1 if glaettung else 2},
                opacity=0.5 if glaettung else 1, showlegend=not glaettung,
                hovertemplate=f"%{{y:+.2f}} {einheit}",
            )
        )  # fmt: skip
        if glaettung:
            glatt = gleitendes_mittel(reihe, glaettung).dropna()
            fig.add_trace(
                go.Scatter(
                    x=glatt.index, y=glatt.values, name=name, legendgroup=gruppe,
                    mode="lines", line={"color": farben[name], "width": 2.5},
                    hovertemplate=f"{glaettung}-j. Mittel %{{y:+.2f}} {einheit}",
                )
            )  # fmt: skip
    if referenz:
        fig.add_vrect(
            x0=referenz[0], x1=referenz[1], fillcolor=stil.REFERENZ_FLAECHE, line_width=0,
            layer="below", annotation_text=f"Referenz {referenz[0]}–{referenz[1]}",
            annotation_position="top", annotation_font={"color": stil.TINTE_GEDAEMPFT, "size": 11},
        )  # fmt: skip
    fig.add_hline(y=0, line={"color": stil.GRUNDLINIE, "width": 1})
    fig.update_layout(
        hovermode="x unified",
        legend={"orientation": "h", "y": -0.15, "x": 0},
        yaxis={
            "title": f"Abweichung ({einheit})",
            "gridcolor": stil.GITTERLINIE,
            "showgrid": True,
            "zeroline": False,
        },
        xaxis={
            "title": None,
            "showspikes": True,
            "spikecolor": stil.GRUNDLINIE,
            "spikethickness": 1,
        },
    )
    return _grundlayout(fig, titel, untertitel)


def stationskarte(
    stationen: pd.DataFrame,
    wert: str,
    titel: str,
    einheit: str,
    untertitel: str | None = None,
    breite: tuple[float, float] = (47.0, 55.2),
    laenge: tuple[float, float] = (5.5, 15.5),
    groesse: str = "temperatur",
) -> go.Figure:
    """Stationskarte mit Hover-Informationen (Name, ID, Höhe, Wert); Farbskala wie statisch."""
    werte = stationen[wert].to_numpy(dtype=float)
    grenze = stil.robuste_grenze(werte)
    hover = (
        "<b>%{customdata[0]}</b> (ID %{customdata[1]})<br>"
        "Höhe: %{customdata[2]:.0f} m<br>"
        f"{wert.capitalize()}: %{{marker.color:+.2f}} {einheit}<extra></extra>"
    )
    fig = go.Figure(
        go.Scattergeo(
            lon=stationen["laenge"], lat=stationen["breite"], mode="markers",
            customdata=stationen[["name", "stations_id", "hoehe"]].to_numpy(),
            hovertemplate=hover,
            marker={
                "size": 9, "color": werte, "colorscale": _plotly_skala(groesse), "cmin": -grenze,
                "cmax": grenze, "line": {"color": stil.FLAECHE, "width": 1},
                "colorbar": {"title": {"text": einheit}, "thickness": 12, "len": 0.6},
            },
        )
    )  # fmt: skip
    fig.update_geos(
        projection_type="mercator", lataxis_range=list(breite), lonaxis_range=list(laenge),
        showcountries=True, countrycolor=stil.TINTE_GEDAEMPFT, showcoastlines=True,
        coastlinecolor=stil.TINTE_GEDAEMPFT, showland=True, landcolor="#f6f5f2",
        showocean=True, oceancolor="#e9eef3", resolution=50, bgcolor=stil.FLAECHE,
    )  # fmt: skip
    fig.update_layout(height=720)
    return _grundlayout(fig, titel, untertitel)


def speichern(fig: go.Figure, name: str, unterordner: str = "") -> Path:
    """Speichert als HTML.

    plotly.js wird vom CDN geladen: Die Datei bleibt klein, die Anzeige braucht aber Internet.
    """
    pfad = stil.ausgabeverzeichnis(unterordner) / f"{name}.html"
    fig.write_html(pfad, include_plotlyjs="cdn", config={"locale": "de"})
    return pfad
