"""Kommandozeile `klima`."""

from __future__ import annotations

from collections import Counter
from typing import Annotated

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
        ergebnisse = lader.lade_datensatz(datensatz, zeitraum)
        zaehler = Counter(e.status for e in ergebnisse)
        typer.echo(
            f"  {len(ergebnisse)} Datei(en): {zaehler['neu']} neu, "
            f"{zaehler['aktualisiert']} aktualisiert, "
            f"{zaehler['unveraendert']} unverändert, {zaehler['fehler']} Fehler"
        )
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
