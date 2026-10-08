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
) -> go.Figure:
    """Interaktiver Jahresverlauf: Überfahren zeigt Jahr, Datum und Wert jeder Linie."""
    from klima.jahresverlauf import MONATSANFAENGE, MONATSNAMEN

    bezeichnungen = bezeichnungen or {}
    tage = matrix.columns.to_numpy()
    # Datum (TT.MM.) je Tag 1–365 im Kalender eines Nicht-Schaltjahres
    daten = pd.date_range("2001-01-01", periods=365).strftime("%d.%m.").to_numpy()
    fig = go.Figure()

    uebrige = [j for j in matrix.index if j not in hervorheben]
    for i, jahr in enumerate(uebrige):
        fig.add_trace(
            go.Scatter(
                x=tage, y=matrix.loc[jahr].to_numpy(), mode="lines", customdata=daten,
                line={"color": "rgba(156,154,147,0.35)", "width": 0.8},
                name=f"{min(uebrige)}–{max(uebrige)}", legendgroup="uebrige",
                showlegend=i == 0,
                hovertemplate=f"<b>{jahr}</b> %{{customdata}}: %{{y:.1f}} {einheit}<extra></extra>",
            )
        )  # fmt: skip
    if referenz is not None:
        fig.add_trace(
            go.Scatter(
                x=referenz.index, y=referenz.to_numpy(), mode="lines", name=referenz_name,
                customdata=daten, line={"color": stil.TINTE, "width": 2},
                hovertemplate=(
                    f"{referenz_name} %{{customdata}}: %{{y:.1f}} {einheit}<extra></extra>"
                ),
            )
        )  # fmt: skip
    farben = stil.farben_fuer([str(j) for j in hervorheben])
    for jahr in hervorheben:
        name = bezeichnungen.get(jahr, str(jahr))
        fig.add_trace(
            go.Scatter(
                x=tage, y=matrix.loc[jahr].to_numpy(), mode="lines", name=name, customdata=daten,
                line={"color": farben[str(jahr)], "width": 2.2},
                hovertemplate=f"<b>{jahr}</b> %{{customdata}}: %{{y:.1f}} {einheit}<extra></extra>",
            )
        )  # fmt: skip

    fig.update_layout(
        hovermode="closest",
        height=640,
        legend={"orientation": "h", "y": -0.12, "x": 0},
        xaxis={
            "range": [1, 365],
            "tickvals": [a + 14.5 for a in MONATSANFAENGE],
            "ticktext": MONATSNAMEN,
            "ticks": "",
            "showgrid": False,
        },
        yaxis={
            "title": f"{y_beschriftung} ({einheit})",
            "gridcolor": stil.GITTERLINIE,
            "showgrid": True,
            "zeroline": False,
        },
    )
    for anfang in MONATSANFAENGE[1:]:
        fig.add_vline(x=anfang, line={"color": stil.GITTERLINIE, "width": 1}, layer="below")
    return _grundlayout(fig, titel, untertitel)


def _zellen_geojson(zellen: pd.DataFrame, groesse: float) -> dict:
    """GeoJSON mit einem Rechteck je Gitterzelle; `id` = "breite_laenge" der Zellmitte."""
    h = groesse / 2
    merkmale = []
    eindeutig = zellen[["zelle_breite", "zelle_laenge"]].drop_duplicates()
    for b, lg in eindeutig.itertuples(index=False):
        ring = [[lg - h, b - h], [lg + h, b - h], [lg + h, b + h], [lg - h, b + h], [lg - h, b - h]]
        merkmale.append(
            {"type": "Feature", "id": f"{b}_{lg}",
             "geometry": {"type": "Polygon", "coordinates": [ring]}}
        )  # fmt: skip
    return {"type": "FeatureCollection", "features": merkmale}


def gitterkarte_zeitregler(
    gitter: pd.DataFrame,
    zeitspalte: str,
    titel: str,
    einheit: str = "°C",
    wert: str = "anomalie",
    zellgroesse: float = 5.0,
    untertitel: str | None = None,
    beschriftung=lambda z: str(z),
) -> go.Figure:
    """Weltkarte der Gitterzellen mit Zeitschieberegler (ein Bild je Wert von `zeitspalte`)."""
    gitter = gitter.assign(
        zelle=gitter["zelle_breite"].astype(str) + "_" + gitter["zelle_laenge"].astype(str)
    )
    geojson = _zellen_geojson(gitter, zellgroesse)
    grenze = stil.robuste_grenze(gitter[wert])
    zeiten = sorted(gitter[zeitspalte].unique())

    def spur(teil: pd.DataFrame) -> go.Choropleth:
        return go.Choropleth(
            geojson=geojson, locations=teil["zelle"], z=teil[wert], zmin=-grenze, zmax=grenze,
            colorscale=_plotly_skala(), marker_line_width=0,
            colorbar={"title": {"text": einheit}, "thickness": 12, "len": 0.6},
            customdata=teil[["zelle_breite", "zelle_laenge"]].to_numpy(),
            hovertemplate=(
                "Zelle %{customdata[0]}° / %{customdata[1]}°<br>"
                f"%{{z:+.2f}} {einheit}<extra></extra>"
            ),
        )  # fmt: skip

    bilder = [go.Frame(data=[spur(gitter[gitter[zeitspalte] == z])], name=str(z)) for z in zeiten]
    fig = go.Figure(data=bilder[-1].data, frames=bilder)
    schritte = [
        {"args": [[str(z)], {"frame": {"duration": 0, "redraw": True}, "mode": "immediate"}],
         "label": beschriftung(z), "method": "animate"}
        for z in zeiten
    ]  # fmt: skip
    fig.update_layout(
        height=640,
        sliders=[{"active": len(zeiten) - 1, "steps": schritte, "x": 0.05, "len": 0.9,
                  "currentvalue": {"prefix": "Zeitraum: "}}],
    )  # fmt: skip
    fig.update_geos(
        projection_type="robinson", showland=True, landcolor="#f6f5f2", showocean=True,
        oceancolor="#e9eef3", showcoastlines=True, coastlinecolor=stil.TINTE_GEDAEMPFT,
        bgcolor=stil.FLAECHE, showframe=False,
    )  # fmt: skip
    return _grundlayout(fig, titel, untertitel)


def weltkarte_stationen(
    stationen: pd.DataFrame, wert: str, titel: str, einheit: str, untertitel: str | None = None
) -> go.Figure:
    """Weltweite Stationskarte mit Hover (Name, ID, Wert); Farbskala robust um 0."""
    werte = stationen[wert].to_numpy(dtype=float)
    grenze = stil.robuste_grenze(werte)
    fig = go.Figure(
        go.Scattergeo(
            lon=stationen["laenge"], lat=stationen["breite"], mode="markers",
            customdata=stationen[["name", "stations_id"]].to_numpy(),
            hovertemplate=(
                "<b>%{customdata[0]}</b> (%{customdata[1]})<br>"
                f"%{{marker.color:+.3f}} {einheit}<extra></extra>"
            ),
            marker={"size": 4, "color": werte, "colorscale": _plotly_skala(), "cmin": -grenze,
                    "cmax": grenze, "colorbar": {"title": {"text": einheit}, "thickness": 12}},
        )
    )  # fmt: skip
    fig.update_geos(
        projection_type="robinson", showland=True, landcolor="#f6f5f2", showocean=True,
        oceancolor="#e9eef3", showcoastlines=True, coastlinecolor=stil.TINTE_GEDAEMPFT,
        bgcolor=stil.FLAECHE, showframe=False,
    )  # fmt: skip
    fig.update_layout(height=620)
    return _grundlayout(fig, titel, untertitel)
