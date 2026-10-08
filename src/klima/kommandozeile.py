"""Kommandozeile `klima`."""

from __future__ import annotations

from collections import Counter
from typing import Annotated

import pandas as pd
import typer

from klima.herunterladen import MANIFEST_NAME, Lader, Manifest, Zeitraum
from klima.konfiguration import lade_quellen, rohverzeichnis

app = typer.Typer(
    help="Klimadaten-Auswertung: Rohdaten laden, aufbereiten, analysieren und darstellen.",
    no_args_is_help=True,
    add_completion=False,
)


@app.callback()
def haupt() -> None:
    """Klimadaten-Auswertung."""


def _groesse_lesbar(anzahl_bytes: int) -> str:
    wert = float(anzahl_bytes)
    for einheit in ("B", "KB", "MB", "GB"):
        if wert < 1024 or einheit == "GB":
            return f"{wert:,.1f} {einheit}".replace(",", "X").replace(".", ",").replace("X", ".")
        wert /= 1024
    raise AssertionError("unerreichbar")


def _liste_ausgeben(quellen: dict, manifest: Manifest) -> None:
    breite = max(len(name) for name in quellen)
    for name, datensatz in quellen.items():
        eintraege = manifest.eintraege_fuer(name)
        if eintraege:
            groesse = sum(e["groesse"] for e in eintraege)
            zuletzt = max(e["geladen_am"] for e in eintraege)[:10]
            lokal = f"{len(eintraege)} Datei(en), {_groesse_lesbar(groesse)}, zuletzt {zuletzt}"
        else:
            lokal = "nicht geladen"
        kennung = "*" if datensatz.standard else " "
        typer.echo(f"{kennung} {name:<{breite}}  {datensatz.beschreibung}")
        typer.echo(f"  {'':<{breite}}  └ lokal: {lokal}")
    typer.echo("\n* = Standardumfang (wird ohne Angabe eines Datensatzes geladen)")


@app.command()
def laden(
    datensaetze: Annotated[
        list[str] | None,
        typer.Argument(help="Namen der Datensätze (siehe --liste). Ohne Angabe: Standardumfang."),
    ] = None,
    alle: Annotated[
        bool, typer.Option("--alle", help="Alle konfigurierten Datensätze laden.")
    ] = False,
    von: Annotated[
        str | None, typer.Option(help="Beginn des Zeitraums, JJJJ oder JJJJ-MM.")
    ] = None,
    bis: Annotated[str | None, typer.Option(help="Ende des Zeitraums, JJJJ oder JJJJ-MM.")] = None,
    erzwingen: Annotated[
        bool, typer.Option("--erzwingen", help="Dateien neu laden, auch wenn sie unverändert sind.")
    ] = False,
    parallel: Annotated[int, typer.Option(help="Anzahl gleichzeitiger Downloads.")] = 8,
    liste: Annotated[
        bool, typer.Option("--liste", help="Verfügbare Datensätze und lokalen Stand anzeigen.")
    ] = False,
    station: Annotated[
        list[str] | None,
        typer.Option(help="Stations-ID für Datensätze vom Typ Stationsauswahl; mehrfach möglich."),
    ] = None,
) -> None:
    """Rohdaten herunterladen."""
    quellen = lade_quellen()
    roh = rohverzeichnis()

    if liste:
        _liste_ausgeben(quellen, Manifest(roh / MANIFEST_NAME))
        return

    if datensaetze:
        unbekannt = [n for n in datensaetze if n not in quellen]
        if unbekannt:
            raise typer.BadParameter(
                f"Unbekannte Datensätze: {', '.join(unbekannt)}. Verfügbar: {', '.join(quellen)}"
            )
        auswahl = [quellen[n] for n in datensaetze]
    elif alle:
        auswahl = list(quellen.values())
    else:
        auswahl = [d for d in quellen.values() if d.standard]

    try:
        zeitraum = Zeitraum.aus_text(von, bis)
    except ValueError as fehler:
        raise typer.BadParameter(str(fehler)) from fehler

    lader = Lader(roh, parallel=parallel, erzwingen=erzwingen)
    fehler_gesamt = 0
    for datensatz in auswahl:
        typer.secho(f"\n▸ {datensatz.name}: {datensatz.beschreibung}", bold=True)
        if not zeitraum.offen and not datensatz.zeitfilter_moeglich:
            typer.echo(
                "  Hinweis: Die Quelle bietet keine zeitliche Einschränkung – "
                "der Gesamtbestand wird geladen, gefiltert wird beim Aufbereiten."
            )
        if datensatz.typ == "stationsauswahl" and not station:
            typer.echo(
                "  Übersprungen: Stations-IDs mit --station angeben (siehe klima ghcnd-suchen)."
            )
            continue
        ergebnisse = lader.lade_datensatz(datensatz, zeitraum, station)
        zaehler = Counter(e.status for e in ergebnisse)
        typer.echo(
            f"  {len(ergebnisse) - zaehler['entfernt']} Datei(en): {zaehler['neu']} neu, "
            f"{zaehler['aktualisiert']} aktualisiert, "
            f"{zaehler['unveraendert']} unverändert, {zaehler['fehler']} Fehler"
        )
        if zaehler["entfernt"]:
            typer.echo(f"  {zaehler['entfernt']} nicht mehr angebotene Datei(en) entfernt")
        for ergebnis in ergebnisse:
            if ergebnis.status == "fehler":
                typer.secho(f"  ✗ {ergebnis.url}: {ergebnis.meldung}", fg=typer.colors.RED)
        fehler_gesamt += zaehler["fehler"]

    typer.echo(f"\nAblage: {roh}")
    if fehler_gesamt:
        raise typer.Exit(code=1)


@app.command()
def aufbereiten(
    datensaetze: Annotated[
        list[str] | None,
        typer.Argument(help="Namen der Datensätze. Ohne Angabe: alle heruntergeladenen."),
    ] = None,
    erzwingen: Annotated[
        bool, typer.Option("--erzwingen", help="Neu aufbereiten, auch wenn alles aktuell ist.")
    ] = False,
) -> None:
    """Rohdaten parsen und als Parquet bzw. NetCDF in `daten/aufbereitet/` ablegen."""
    # Erst hier importieren: pandas/xarray verlangsamen sonst den Start von `klima laden`
    from klima.aufbereiten import AUFBEREITER, Aufbereitung
    from klima.einlesen import aufbereitungsverzeichnis

    if datensaetze:
        unbekannt = [n for n in datensaetze if n not in AUFBEREITER]
        if unbekannt:
            raise typer.BadParameter(
                f"Keine Aufbereitung für: {', '.join(unbekannt)}. "
                f"Verfügbar: {', '.join(AUFBEREITER)}"
            )
        auswahl = list(datensaetze)
    else:
        auswahl = list(AUFBEREITER)

    aufbereitung = Aufbereitung(rohverzeichnis(), aufbereitungsverzeichnis())
    texte = {
        "aufbereitet": "aufbereitet",
        "aktuell": "bereits aktuell",
        "keine_rohdaten": "übersprungen, keine Rohdaten (erst `klima laden`)",
    }
    for name in auswahl:
        typer.echo(f"▸ {name}: ", nl=False)
        ergebnis = aufbereitung.aufbereiten(name, erzwingen=erzwingen)
        groesse = sum(p.stat().st_size for p in ergebnis.dateien)
        dateien = ", ".join(p.name for p in ergebnis.dateien)
        zusatz = f" – {dateien} ({_groesse_lesbar(groesse)})" if ergebnis.dateien else ""
        typer.echo(texte[ergebnis.status] + zusatz)
    typer.echo(f"\nAblage: {aufbereitungsverzeichnis()}")


analysieren_app = typer.Typer(help="Auswertungen rechnen und Grafiken nach `ausgabe/` schreiben.")
app.add_typer(analysieren_app, name="analysieren")


def _referenz(von: int | None, bis: int | None) -> tuple[int, int] | None:
    if (von is None) != (bis is None):
        raise typer.BadParameter("--referenz-von und --referenz-bis nur gemeinsam angeben.")
    return (von, bis) if von is not None and bis is not None else None


def _trends_ausgeben(ergebnis) -> None:
    for name, trend in ergebnis.trends.items():
        einheit = ergebnis.einheiten.get(name) or ("%" if name.startswith("Niederschlag") else "°C")
        typer.echo(f"  {name}: {trend.text(einheit)}")
    typer.echo(f"\n{len(ergebnis.dateien)} Datei(en) geschrieben, z. B. {ergebnis.dateien[0]}")


ReferenzVon = Annotated[
    int | None, typer.Option(help="Beginn der Referenzperiode (Standard aus analyse.toml).")
]
ReferenzBis = Annotated[int | None, typer.Option(help="Ende der Referenzperiode.")]
TrendVon = Annotated[int, typer.Option(help="Beginn des Trendzeitraums.")]


@analysieren_app.command("deutschland")
def analysieren_deutschland(
    trend_von: TrendVon = 1951,
    referenz_von: ReferenzVon = None,
    referenz_bis: ReferenzBis = None,
) -> None:
    """Temperatur und Niederschlag in Deutschland: eigene Gebietsmittel vs. DWD."""
    from klima import auswertungen

    ergebnis = auswertungen.deutschland(trend_von, _referenz(referenz_von, referenz_bis))
    typer.secho("Trends Deutschland:", bold=True)
    _trends_ausgeben(ergebnis)


@analysieren_app.command("station")
def analysieren_station(
    station: Annotated[str, typer.Argument(help="DWD-Stations-ID (z. B. 3987) oder Namensteil.")],
    trend_von: TrendVon = 1951,
    referenz_von: ReferenzVon = None,
    referenz_bis: ReferenzBis = None,
) -> None:
    """Temperatur und Niederschlag einer DWD-Station."""
    from klima import auswertungen, deutschland

    if station.isdigit():
        stations_id = station.zfill(5)
    else:
        treffer = deutschland.station_suchen(station)
        if treffer.empty:
            raise typer.BadParameter(f"Keine DWD-Station mit {station!r} im Namen gefunden.")
        if len(treffer) > 1:
            typer.echo("Mehrere Stationen gefunden, bitte ID angeben:")
            for _, zeile in treffer.iterrows():
                typer.echo(
                    f"  {zeile.stations_id}  {zeile['name']}  "
                    f"({zeile.von:%Y}–{zeile.bis:%Y}, {zeile.bundesland})"
                )
            raise typer.Exit(code=1)
        stations_id = treffer.iloc[0]["stations_id"]

    ergebnis = auswertungen.station(stations_id, trend_von, _referenz(referenz_von, referenz_bis))
    typer.secho(f"Trends Station {stations_id}:", bold=True)
    _trends_ausgeben(ergebnis)


# Kurzformen der Messgrößen für die Terminalausgabe
_MESSGROESSEN_KURZ = {
    "Temperatur-Maximum": "Tmax",
    "Temperatur-Minimum": "Tmin",
    "Temperatur": "T",
    "Niederschlag": "N",
    "Sonnenschein": "S",
    "Schneehöhe": "Sh",
}


def _datum_je_aufloesung(tabelle, spalte: str):
    """Monatswerte als `JJJJ-MM`, Tageswerte als `TT.MM.JJJJ`."""
    monatlich = tabelle["aufloesung"] == "monatlich"
    return (
        tabelle[spalte]
        .dt.strftime("%d.%m.%Y")
        .where(~monatlich, tabelle[spalte].dt.strftime("%Y-%m"))
    )


@app.command()
def stationen(
    land: Annotated[
        list[str] | None,
        typer.Option(help="FIPS-Ländercode (GM) oder Teil des Ländernamens; mehrfach möglich."),
    ] = None,
    quelle: Annotated[
        list[str] | None,
        typer.Option(
            help="ghcnm_qcu, ghcnm_qcf, ghcnm_qfe, dwd_monat, dwd_tag, ghcnd; mehrfach möglich."
        ),
    ] = None,
    name: Annotated[str | None, typer.Option(help="Teil des Stationsnamens.")] = None,
    aufloesung: Annotated[
        str | None, typer.Option(help="Zeitliche Auflösung, z. B. monatlich.")
    ] = None,
    export: Annotated[
        str | None, typer.Option(help="Ergebnis speichern als .csv (Excel-tauglich) oder .parquet.")
    ] = None,
    anzahl: Annotated[int, typer.Option(help="Maximal angezeigte Zeilen (0 = alle).")] = 50,
) -> None:
    """Übersicht der lokal vorhandenen Messstationen: Land, Name, Auflösung, Zeitraum."""
    from pathlib import Path

    from klima.bestand import stationsuebersicht, zusammenfassung

    uebersicht = stationsuebersicht(quelle, land, name, aufloesung)
    if uebersicht.empty:
        typer.echo("Keine Stationen gefunden (Filter prüfen oder erst `klima laden`).")
        raise typer.Exit(code=1)

    typer.secho("Bestand je Quelle:", bold=True)
    for zeile in zusammenfassung(uebersicht).itertuples():
        typer.echo(
            f"  {zeile.quelle:<10} {zeile.aufloesung:<10} {zeile.stationen:>6} Stationen in "
            f"{zeile.laender:>3} Ländern, {zeile.von:%d.%m.%Y}–{zeile.bis:%d.%m.%Y}, "
            f"{f'{zeile.werte:,}'.replace(',', '.')} Werte"
        )

    anzeige = uebersicht.assign(
        land=uebersicht["land"].astype(str) + " " + uebersicht["land_name"].fillna(""),
        region=uebersicht["region"].fillna(""),
        vollst=uebersicht["vollstaendigkeit"].map(lambda v: f"{v:.0f} %"),
        messgroessen=uebersicht["messgroessen"].replace(_MESSGROESSEN_KURZ, regex=True),
        von=_datum_je_aufloesung(uebersicht, "von"),
        bis=_datum_je_aufloesung(uebersicht, "bis"),
    )[["quelle", "stations_id", "name", "land", "region", "aufloesung", "messgroessen",
       "von", "bis", "vollst"]]  # fmt: skip
    anzeige.columns = ["Quelle", "ID", "Name", "Land", "Region", "Auflösung", "Messgrößen",
                       "von", "bis", "vollst."]  # fmt: skip
    gekuerzt = anzahl and len(anzeige) > anzahl
    typer.echo("")
    typer.echo((anzeige.head(anzahl) if gekuerzt else anzeige).to_string(index=False))
    if gekuerzt:
        typer.echo(f"… {len(anzeige) - anzahl} weitere Zeilen (--anzahl 0 zeigt alle)")
    typer.echo(
        "Messgrößen: T Temperatur, Tmax/Tmin Maximum/Minimum, N Niederschlag, S Sonnenschein, "
        "Sh Schneehöhe"
    )

    if export:
        ziel = Path(export)
        if ziel.suffix == ".parquet":
            uebersicht.to_parquet(ziel, index=False)
        elif ziel.suffix == ".csv":
            uebersicht.assign(
                von=uebersicht["von"].astype(str), bis=uebersicht["bis"].astype(str)
            ).to_csv(ziel, sep=";", decimal=",", index=False, encoding="utf-8-sig")
        else:
            raise typer.BadParameter("Export nur als .csv oder .parquet.")
        typer.echo(f"\n{len(uebersicht)} Zeilen gespeichert: {ziel}")


@analysieren_app.command("jahresverlauf")
def analysieren_jahresverlauf(
    hervorheben: Annotated[int, typer.Option(help="Anzahl der letzten Jahre in Farbe.")] = 5,
    ab_jahr: Annotated[int, typer.Option(help="Erstes dargestelltes Jahr.")] = 1881,
    referenz_von: ReferenzVon = None,
    referenz_bis: ReferenzBis = None,
) -> None:
    """Tagesmitteltemperatur Deutschland: jedes Jahr eine Linie über Tag 1–365."""
    from klima import auswertungen

    ergebnis = auswertungen.jahresverlauf_deutschland(
        hervorheben=hervorheben,
        ab_jahr=ab_jahr,
        referenz=_referenz(referenz_von, referenz_bis),
    )
    matrix = ergebnis.tabellen["jahresmatrix"]
    typer.echo(f"{len(matrix)} Jahre ({matrix.index.min()}–{matrix.index.max()}) dargestellt")
    for pfad in ergebnis.dateien:
        typer.echo(f"  {pfad}")


@analysieren_app.command("global")
def analysieren_global(
    trend_von: TrendVon = 1951,
    referenz_von: ReferenzVon = None,
    referenz_bis: ReferenzBis = None,
) -> None:
    """Globale Landtemperatur aus GHCNm: unbereinigt vs. homogenisiert, Vergleich mit GISTEMP."""
    from klima import auswertungen

    ergebnis = auswertungen.weltweit_land(trend_von, _referenz(referenz_von, referenz_bis))
    typer.secho("Trends globale Landtemperatur:", bold=True)
    _trends_ausgeben(ergebnis)


@analysieren_app.command("land-ozean")
def analysieren_land_ozean(
    trend_von: TrendVon = 1951,
    referenz_von: ReferenzVon = None,
    referenz_bis: ReferenzBis = None,
) -> None:
    """Globale Temperatur aus Land (GHCNm) und Ozean (ERSST) vs. GISTEMP und HadCRUT5."""
    from klima import auswertungen

    ergebnis = auswertungen.land_ozean(trend_von, _referenz(referenz_von, referenz_bis))
    typer.secho("Trends globale Temperatur (Land + Ozean):", bold=True)
    _trends_ausgeben(ergebnis)


@analysieren_app.command("kenntage")
def analysieren_kenntage(
    trend_von: TrendVon = 1951,
    referenz_von: ReferenzVon = None,
    referenz_bis: ReferenzBis = None,
) -> None:
    """Kenntage, Hitzewellen und Niederschlagsextreme in Deutschland aus DWD-Tageswerten."""
    from klima import auswertungen

    ergebnis = auswertungen.kenntage_deutschland(trend_von, _referenz(referenz_von, referenz_bis))
    typer.secho("Trends Deutschland (eigene Berechnung und DWD):", bold=True)
    _trends_ausgeben(ergebnis)


@app.command("ghcnd-suchen")
def ghcnd_suchen(
    land: Annotated[str | None, typer.Option(help="FIPS-Ländercode, z. B. US, SZ, AS.")] = None,
    name: Annotated[str | None, typer.Option(help="Teil des Stationsnamens.")] = None,
    seit: Annotated[int | None, typer.Option(help="Daten spätestens ab diesem Jahr.")] = None,
    bis_mindestens: Annotated[
        int | None, typer.Option(help="Daten mindestens bis zu diesem Jahr.")
    ] = None,
    anzahl: Annotated[int, typer.Option(help="Maximal angezeigte Stationen.")] = 30,
) -> None:
    """GHCN-Daily-Stationen mit Temperatur (TMAX/TMIN) und Niederschlag suchen."""
    from klima import einlesen

    stationen = einlesen.ghcnd_stationen([land.upper()] if land else None)
    if name:
        stationen = stationen[stationen["name"].str.contains(name, case=False, regex=False)]
    inventar = einlesen.ghcnd_inventar(["TMAX", "TMIN", "PRCP"])
    inventar = inventar[inventar["stations_id"].isin(stationen["stations_id"])]
    zeitraum = inventar.pivot_table(
        index="stations_id", columns="element", values=["von", "bis"], observed=True
    )
    zeitraum.columns = [f"{e}_{w}" for w, e in zeitraum.columns]
    ergebnis = stationen.merge(zeitraum.reset_index(), on="stations_id")
    for element in ("TMAX", "TMIN", "PRCP"):
        if f"{element}_von" not in ergebnis:
            ergebnis[f"{element}_von"] = pd.NA
            ergebnis[f"{element}_bis"] = pd.NA
    ergebnis = ergebnis.dropna(subset=["TMAX_von", "TMIN_von"])
    if seit is not None:
        ergebnis = ergebnis[ergebnis["TMAX_von"] <= seit]
    if bis_mindestens is not None:
        ergebnis = ergebnis[ergebnis["TMAX_bis"] >= bis_mindestens]
    ergebnis = ergebnis.assign(dauer=ergebnis["TMAX_bis"] - ergebnis["TMAX_von"])
    ergebnis = ergebnis.sort_values("dauer", ascending=False)
    if ergebnis.empty:
        typer.echo("Keine passenden Stationen (erst `klima laden ghcnd_stationen`?).")
        raise typer.Exit(code=1)

    anzeige = ergebnis.head(anzahl)
    typer.echo(f"{len(ergebnis)} Stationen gefunden, längste Temperaturreihen zuerst:\n")
    for zeile in anzeige.itertuples():
        niederschlag = (
            f"{int(zeile.PRCP_von)}–{int(zeile.PRCP_bis)}" if pd.notna(zeile.PRCP_von) else "–"
        )
        typer.echo(
            f"  {zeile.stations_id}  {zeile.name[:30]:<30}  Temperatur "
            f"{int(zeile.TMAX_von)}–{int(zeile.TMAX_bis)}  Niederschlag {niederschlag}"
        )
    typer.echo(
        "\nLaden z. B.: uv run klima laden ghcnd_tageswerte "
        f"--station {anzeige.iloc[0].stations_id}"
    )


@analysieren_app.command("kenntage-station")
def analysieren_kenntage_station(
    station: Annotated[
        str, typer.Argument(help="DWD-ID (z. B. 3987) oder GHCN-Daily-ID (z. B. USW00094728).")
    ],
    trend_von: TrendVon = 1951,
    referenz_von: ReferenzVon = None,
    referenz_bis: ReferenzBis = None,
) -> None:
    """Kenntage und Niederschlagsextreme einer einzelnen Station (DWD oder GHCN-Daily)."""
    from klima import auswertungen

    try:
        ergebnis = auswertungen.kenntage_station(
            station, trend_von, _referenz(referenz_von, referenz_bis)
        )
    except ValueError as fehler:
        raise typer.BadParameter(str(fehler)) from fehler
    typer.secho(f"Trends Station {station}:", bold=True)
    _trends_ausgeben(ergebnis)
